"""Conservative automated site-check provider.

This provider only reads publicly returned pages and extracts machine-readable
JSON-LD flight offers. It does not log in, solve CAPTCHA challenges, spoof a
browser, or bypass site protections.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from typing import Any

import requests

from storage import FlightOffer

from .base_provider import (
    FlightProvider,
    ProviderAuthenticationError,
    ProviderNetworkError,
    ProviderResponseError,
)
from .site_sources import DEFAULT_FLIGHT_SEARCH_SITES, FlightSearchSite


AUTOMATED_SITE_PROVIDER_PREFIX = "automated_site_check:"
BLOCKED_PAGE_MARKERS = (
    "captcha",
    "access denied",
    "unusual traffic",
    "are you a robot",
    "verify you are human",
)


class AutomatedSiteFlightProvider(FlightProvider):
    """Check configured travel sites for machine-readable flight offers."""

    source_provider = "automated_site_check"

    def __init__(
        self,
        sites: tuple[FlightSearchSite, ...] = DEFAULT_FLIGHT_SEARCH_SITES,
        timeout_seconds: float = 20,
        session: requests.Session | None = None,
        page_fetcher: Callable[[str], str] | None = None,
    ) -> None:
        self.sites = sites
        self.timeout_seconds = timeout_seconds
        self.session = session or requests.Session()
        self.page_fetcher = page_fetcher

    def search_flights(
        self,
        origin: str,
        destination: str,
        departure_date: date,
        return_date: date | None,
        max_price: Decimal | None,
        currency: str,
    ) -> list[FlightOffer]:
        offers: list[FlightOffer] = []
        errors = []
        for site in self.sites:
            url = site.build_url(origin, destination, departure_date, return_date, currency)
            try:
                html = self._fetch_page(url)
                self._raise_if_blocked(html, site.display_name)
                offers.extend(
                    _offers_from_json_ld(
                        html=html,
                        site=site,
                        source_url=url,
                        requested_origin=origin,
                        requested_destination=destination,
                        requested_currency=currency,
                    )
                )
            except (ProviderAuthenticationError, ProviderNetworkError) as exc:
                errors.append(str(exc))

        if offers:
            return offers
        if errors:
            raise ProviderResponseError(
                "Automated site checks could not read fare data. "
                + " | ".join(dict.fromkeys(errors))
            )
        return []

    def _fetch_page(self, url: str) -> str:
        if self.page_fetcher is not None:
            return self.page_fetcher(url)
        try:
            response = self.session.get(
                url,
                headers={"User-Agent": "FlightSearcher/1.0"},
                timeout=self.timeout_seconds,
            )
        except requests.Timeout as exc:
            raise ProviderNetworkError("Automated site check timed out.") from exc
        except requests.RequestException as exc:
            raise ProviderNetworkError("Automated site check failed.") from exc

        if response.status_code in {401, 403, 429}:
            raise ProviderAuthenticationError(
                f"Automated site check was blocked with status {response.status_code}."
            )
        if response.status_code >= 400:
            raise ProviderNetworkError(
                f"Automated site check failed with status {response.status_code}."
            )
        return response.text

    @staticmethod
    def _raise_if_blocked(html: str, site_name: str) -> None:
        lower_html = html.lower()
        if any(marker in lower_html for marker in BLOCKED_PAGE_MARKERS):
            raise ProviderAuthenticationError(
                f"{site_name} returned a human-verification or blocked page."
            )


class _JsonLdScriptParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_json_ld_script = False
        self.current_chunks: list[str] = []
        self.scripts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "script":
            return
        attrs_dict = {key.lower(): value or "" for key, value in attrs}
        script_type = attrs_dict.get("type", "").lower()
        if "application/ld+json" in script_type:
            self.in_json_ld_script = True
            self.current_chunks = []

    def handle_data(self, data: str) -> None:
        if self.in_json_ld_script:
            self.current_chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "script" and self.in_json_ld_script:
            self.scripts.append("".join(self.current_chunks))
            self.in_json_ld_script = False
            self.current_chunks = []


def _offers_from_json_ld(
    html: str,
    site: FlightSearchSite,
    source_url: str,
    requested_origin: str,
    requested_destination: str,
    requested_currency: str,
) -> list[FlightOffer]:
    offers = []
    for node in _json_ld_nodes(html):
        if not _is_flight_like_node(node):
            continue
        for raw_offer in _as_list(node.get("offers")):
            mapped_offer = _map_json_ld_offer(
                node=node,
                raw_offer=raw_offer,
                site=site,
                source_url=source_url,
                requested_origin=requested_origin,
                requested_destination=requested_destination,
                requested_currency=requested_currency,
            )
            if mapped_offer is not None:
                offers.append(mapped_offer)
    return offers


def _json_ld_nodes(html: str) -> list[dict[str, Any]]:
    parser = _JsonLdScriptParser()
    parser.feed(html)
    nodes: list[dict[str, Any]] = []
    for script in parser.scripts:
        try:
            payload = json.loads(script)
        except json.JSONDecodeError:
            continue
        nodes.extend(_flatten_json_ld(payload))
    return nodes


def _flatten_json_ld(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        nodes = []
        for item in payload:
            nodes.extend(_flatten_json_ld(item))
        return nodes
    if not isinstance(payload, dict):
        return []
    graph = payload.get("@graph")
    nodes = [payload]
    if isinstance(graph, list):
        nodes.extend(item for item in graph if isinstance(item, dict))
    return nodes


def _is_flight_like_node(node: dict[str, Any]) -> bool:
    node_types = {str(item).lower() for item in _as_list(node.get("@type"))}
    return "flight" in node_types or (
        bool(node.get("offers"))
        and bool(node.get("departureTime") or node.get("departure_time"))
        and bool(node.get("arrivalTime") or node.get("arrival_time"))
    )


def _map_json_ld_offer(
    node: dict[str, Any],
    raw_offer: Any,
    site: FlightSearchSite,
    source_url: str,
    requested_origin: str,
    requested_destination: str,
    requested_currency: str,
) -> FlightOffer | None:
    if not isinstance(raw_offer, dict):
        return None
    try:
        departure_time = _parse_datetime(node["departureTime"])
        arrival_time = _parse_datetime(node["arrivalTime"])
        price = _parse_price(raw_offer["price"])
    except (KeyError, TypeError, ValueError, InvalidOperation):
        return None

    return FlightOffer(
        airline=_airline_name(node),
        origin=_airport_code(node.get("departureAirport"), requested_origin),
        destination=_airport_code(node.get("arrivalAirport"), requested_destination),
        departure_time=departure_time,
        arrival_time=arrival_time,
        duration=_duration_text(departure_time, arrival_time),
        number_of_stops=0,
        price=price,
        currency=str(raw_offer.get("priceCurrency") or requested_currency).upper(),
        booking_url=str(raw_offer.get("url") or source_url),
        source_provider=f"{AUTOMATED_SITE_PROVIDER_PREFIX}{site.key}",
    )


def _airline_name(node: dict[str, Any]) -> str:
    airline = node.get("airline") or node.get("provider")
    if isinstance(airline, dict):
        return str(airline.get("name") or airline.get("iataCode") or "Unknown")
    if isinstance(airline, list) and airline:
        first_airline = airline[0]
        if isinstance(first_airline, dict):
            return str(first_airline.get("name") or first_airline.get("iataCode") or "Unknown")
        return str(first_airline)
    if airline:
        return str(airline)
    name = node.get("name")
    return str(name) if name else "Unknown"


def _airport_code(value: Any, fallback: str) -> str:
    if isinstance(value, dict):
        return str(value.get("iataCode") or value.get("identifier") or fallback).upper()
    if isinstance(value, str) and len(value.strip()) == 3:
        return value.strip().upper()
    return fallback.upper()


def _parse_datetime(value: Any) -> datetime:
    if not isinstance(value, str):
        raise TypeError("Datetime value must be a string.")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _parse_price(value: Any) -> Decimal:
    if isinstance(value, str):
        value = value.replace(",", "").strip()
    return Decimal(str(value))


def _duration_text(departure_time: datetime, arrival_time: datetime) -> str:
    total_minutes = int((arrival_time - departure_time).total_seconds() // 60)
    if total_minutes <= 0:
        return ""
    hours, minutes = divmod(total_minutes, 60)
    if hours and minutes:
        return f"{hours}h {minutes}m"
    if hours:
        return f"{hours}h"
    return f"{minutes}m"


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]
