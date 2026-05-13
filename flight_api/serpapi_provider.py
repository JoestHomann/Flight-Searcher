"""SerpApi Google Flights provider."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

import requests

from storage import FlightOffer

from .base_provider import (
    FlightProvider,
    MissingCredentialsError,
    ProviderAuthenticationError,
    ProviderNetworkError,
    ProviderRateLimitError,
    ProviderResponseError,
)


class SerpApiGoogleFlightsProvider(FlightProvider):
    source_provider = "serpapi_google_flights"

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://serpapi.com/search",
        timeout_seconds: float = 20,
        session: requests.Session | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds
        self.session = session or requests.Session()

    def search_flights(
        self,
        origin: str,
        destination: str,
        departure_date: date,
        return_date: date | None,
        max_price: Decimal | None,
        currency: str,
    ) -> list[FlightOffer]:
        if not self.api_key:
            raise MissingCredentialsError(
                "SerpApi API key is missing. Set SERPAPI_API_KEY in .env."
            )

        params: dict[str, Any] = {
            "engine": "google_flights",
            "api_key": self.api_key,
            "departure_id": origin,
            "arrival_id": destination,
            "outbound_date": departure_date.isoformat(),
            "currency": currency,
            "adults": 1,
            "sort_by": 2,
            "type": 1 if return_date else 2,
        }
        if return_date is not None:
            params["return_date"] = return_date.isoformat()
        if max_price is not None:
            params["max_price"] = str(max_price)

        response = self._request(params)
        payload = self._json_payload(response)
        if payload.get("error"):
            raise ProviderResponseError(str(payload["error"]))

        search_url = self._search_url(payload)
        raw_offers = self._raw_offers(payload)
        return [self._map_offer(offer, currency, search_url) for offer in raw_offers]

    def _request(self, params: dict[str, Any]) -> requests.Response:
        try:
            response = self.session.get(
                self.base_url,
                params=params,
                timeout=self.timeout_seconds,
            )
        except requests.Timeout as exc:
            raise ProviderNetworkError("SerpApi Google Flights request timed out.") from exc
        except requests.RequestException as exc:
            raise ProviderNetworkError("Could not reach SerpApi.") from exc

        if response.status_code in {400, 401, 403}:
            raise ProviderAuthenticationError(
                "SerpApi rejected the API key or request."
            )
        if response.status_code == 429:
            raise ProviderRateLimitError("SerpApi rate limit reached.")
        if response.status_code >= 400:
            raise ProviderNetworkError(
                f"SerpApi request failed with status {response.status_code}."
            )
        return response

    @staticmethod
    def _json_payload(response: requests.Response) -> dict[str, Any]:
        try:
            payload = response.json()
        except ValueError as exc:
            raise ProviderResponseError("SerpApi returned invalid JSON.") from exc
        if not isinstance(payload, dict):
            raise ProviderResponseError("SerpApi returned an unexpected response.")
        return payload

    @staticmethod
    def _raw_offers(payload: dict[str, Any]) -> list[dict[str, Any]]:
        raw_offers = []
        for key in ("best_flights", "other_flights"):
            value = payload.get(key, [])
            if isinstance(value, list):
                raw_offers.extend(item for item in value if isinstance(item, dict))
        return raw_offers

    @staticmethod
    def _search_url(payload: dict[str, Any]) -> str | None:
        metadata = payload.get("search_metadata", {})
        if isinstance(metadata, dict):
            url = metadata.get("google_flights_url")
            if isinstance(url, str) and url:
                return url
        return None

    def _map_offer(
        self,
        offer: dict[str, Any],
        requested_currency: str,
        search_url: str | None,
    ) -> FlightOffer:
        try:
            flights = offer["flights"]
            first_flight = flights[0]
            last_flight = flights[-1]
            departure_airport = first_flight["departure_airport"]
            arrival_airport = last_flight["arrival_airport"]
            total_duration = int(
                offer.get("total_duration") or self._segment_duration_minutes(flights)
            )
            return FlightOffer(
                airline=self._airline_name(flights),
                origin=departure_airport["id"],
                destination=arrival_airport["id"],
                departure_time=self._parse_time(departure_airport["time"]),
                arrival_time=self._parse_time(arrival_airport["time"]),
                duration=self._format_minutes(total_duration),
                number_of_stops=max(len(flights) - 1, 0),
                price=self._parse_price(offer["price"]),
                currency=requested_currency,
                booking_url=search_url,
                source_provider=self.source_provider,
            )
        except (KeyError, IndexError, TypeError, ValueError, InvalidOperation) as exc:
            raise ProviderResponseError(
                "SerpApi returned a flight offer with an unexpected format."
            ) from exc

    @staticmethod
    def _airline_name(flights: list[dict[str, Any]]) -> str:
        airlines = []
        for flight in flights:
            airline = flight.get("airline")
            if airline and airline not in airlines:
                airlines.append(airline)
        return ", ".join(airlines) if airlines else "Unknown"

    @staticmethod
    def _parse_time(value: str) -> datetime:
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        return datetime.fromisoformat(value)

    @staticmethod
    def _parse_price(value: Any) -> Decimal:
        if isinstance(value, str):
            value = value.replace("$", "").replace(",", "").strip()
        return Decimal(str(value))

    @staticmethod
    def _segment_duration_minutes(flights: list[dict[str, Any]]) -> int:
        return sum(int(flight.get("duration", 0)) for flight in flights)

    @staticmethod
    def _format_minutes(minutes: int) -> str:
        duration = timedelta(minutes=minutes)
        total_minutes = int(duration.total_seconds() // 60)
        hours, remaining_minutes = divmod(total_minutes, 60)
        if hours and remaining_minutes:
            return f"{hours}h {remaining_minutes}m"
        if hours:
            return f"{hours}h"
        return f"{remaining_minutes}m"
