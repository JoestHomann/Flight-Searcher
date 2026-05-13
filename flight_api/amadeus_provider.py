"""Amadeus Self-Service Flight Offers provider."""

from __future__ import annotations

import re
import time
from datetime import date, datetime
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


class AmadeusProvider(FlightProvider):
    source_provider = "amadeus"

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        base_url: str = "https://test.api.amadeus.com",
        timeout_seconds: float = 20,
        session: requests.Session | None = None,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.session = session or requests.Session()
        self._access_token: str | None = None
        self._token_expires_at = 0.0

    def search_flights(
        self,
        origin: str,
        destination: str,
        departure_date: date,
        return_date: date | None,
        max_price: Decimal | None,
        currency: str,
    ) -> list[FlightOffer]:
        token = self._get_access_token()
        params = {
            "originLocationCode": origin,
            "destinationLocationCode": destination,
            "departureDate": departure_date.isoformat(),
            "adults": 1,
            "currencyCode": currency,
            "max": 20,
        }
        if return_date is not None:
            params["returnDate"] = return_date.isoformat()
        if max_price is not None:
            params["maxPrice"] = str(max_price)

        response = self._request(
            "get",
            f"{self.base_url}/v2/shopping/flight-offers",
            headers={"Authorization": f"Bearer {token}"},
            params=params,
        )
        payload = self._json_payload(response)
        data = payload.get("data", [])
        if not isinstance(data, list):
            raise ProviderResponseError("Amadeus returned an unexpected response.")
        dictionaries = payload.get("dictionaries", {})
        carriers = dictionaries.get("carriers", {}) if isinstance(dictionaries, dict) else {}
        return [self._map_offer(offer, carriers, currency) for offer in data]

    def _get_access_token(self) -> str:
        if not self.client_id or not self.client_secret:
            raise MissingCredentialsError(
                "Amadeus API credentials are missing. Set AMADEUS_CLIENT_ID and "
                "AMADEUS_CLIENT_SECRET in .env."
            )
        if self._access_token and time.time() < self._token_expires_at:
            return self._access_token

        response = self._request(
            "post",
            f"{self.base_url}/v1/security/oauth2/token",
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
        )
        payload = self._json_payload(response)
        access_token = payload.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise ProviderResponseError("Amadeus did not return an access token.")
        expires_in = int(payload.get("expires_in", 1799))
        self._access_token = access_token
        self._token_expires_at = time.time() + max(expires_in - 60, 60)
        return access_token

    def _request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        try:
            response = getattr(self.session, method)(
                url,
                timeout=self.timeout_seconds,
                **kwargs,
            )
        except requests.Timeout as exc:
            raise ProviderNetworkError("Amadeus request timed out.") from exc
        except requests.RequestException as exc:
            raise ProviderNetworkError("Could not reach Amadeus API.") from exc

        if response.status_code in {400, 401, 403}:
            raise ProviderAuthenticationError(
                "Amadeus rejected the API credentials or request."
            )
        if response.status_code == 429:
            raise ProviderRateLimitError("Amadeus API rate limit reached.")
        if response.status_code >= 400:
            raise ProviderNetworkError(
                f"Amadeus API request failed with status {response.status_code}."
            )
        return response

    @staticmethod
    def _json_payload(response: requests.Response) -> dict[str, Any]:
        try:
            payload = response.json()
        except ValueError as exc:
            raise ProviderResponseError("Amadeus returned invalid JSON.") from exc
        if not isinstance(payload, dict):
            raise ProviderResponseError("Amadeus returned an unexpected response.")
        return payload

    def _map_offer(
        self,
        offer: dict[str, Any],
        carriers: dict[str, str],
        requested_currency: str,
    ) -> FlightOffer:
        try:
            itinerary = offer["itineraries"][0]
            segments = itinerary["segments"]
            first_segment = segments[0]
            last_segment = segments[-1]
            price = offer["price"]
            airline_code = self._airline_code(offer, first_segment)
            return FlightOffer(
                airline=carriers.get(airline_code, airline_code),
                origin=first_segment["departure"]["iataCode"],
                destination=last_segment["arrival"]["iataCode"],
                departure_time=datetime.fromisoformat(
                    first_segment["departure"]["at"]
                ),
                arrival_time=datetime.fromisoformat(last_segment["arrival"]["at"]),
                duration=self._format_duration(itinerary.get("duration", "")),
                number_of_stops=max(len(segments) - 1, 0),
                price=Decimal(price.get("grandTotal") or price["total"]),
                currency=price.get("currency", requested_currency),
                booking_url=None,
                source_provider=self.source_provider,
            )
        except (KeyError, IndexError, TypeError, InvalidOperation, ValueError) as exc:
            raise ProviderResponseError(
                "Amadeus returned a flight offer with an unexpected format."
            ) from exc

    @staticmethod
    def _airline_code(offer: dict[str, Any], first_segment: dict[str, Any]) -> str:
        validating_codes = offer.get("validatingAirlineCodes") or []
        if validating_codes:
            return validating_codes[0]
        return first_segment.get("carrierCode", "Unknown")

    @staticmethod
    def _format_duration(duration: str) -> str:
        match = re.fullmatch(r"P(?:T)?(?:(\d+)H)?(?:(\d+)M)?", duration)
        if not match:
            return duration
        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        parts = []
        if hours:
            parts.append(f"{hours}h")
        if minutes:
            parts.append(f"{minutes}m")
        return " ".join(parts) or "0m"
