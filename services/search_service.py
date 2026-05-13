"""Search orchestration and validation for flight offers."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

from flight_api import FlightProvider
from storage import FlightOffer


class SearchValidationError(ValueError):
    """Raised when search input cannot be used safely."""


class SearchService:
    def __init__(self, provider: FlightProvider) -> None:
        self.provider = provider

    def search(
        self,
        origin: str,
        destination: str,
        departure_date: str | date,
        return_date: str | date | None = None,
        is_round_trip: bool = False,
        max_price: str | Decimal | None = None,
        currency: str = "EUR",
    ) -> list[FlightOffer]:
        clean_origin = self._required_text(origin, "Origin")
        clean_destination = self._required_text(destination, "Destination")
        clean_departure_date = self._parse_date(departure_date, "Departure date")
        clean_return_date = self._parse_optional_return_date(
            return_date, is_round_trip
        )
        clean_max_price = self._parse_optional_price(max_price)
        clean_currency = (currency or "EUR").strip().upper()

        offers = self.provider.search_flights(
            origin=clean_origin,
            destination=clean_destination,
            departure_date=clean_departure_date,
            return_date=clean_return_date,
            max_price=clean_max_price,
            currency=clean_currency,
        )
        filtered_offers = self._filter_by_max_price(offers, clean_max_price)
        return sorted(filtered_offers, key=lambda offer: offer.price)

    @staticmethod
    def _required_text(value: str, field_name: str) -> str:
        clean_value = value.strip()
        if not clean_value:
            raise SearchValidationError(f"{field_name} must not be empty.")
        return clean_value.upper()

    @staticmethod
    def _parse_date(value: str | date, field_name: str) -> date:
        if isinstance(value, date):
            return value
        clean_value = value.strip()
        try:
            return date.fromisoformat(clean_value)
        except ValueError as exc:
            raise SearchValidationError(
                f"{field_name} must use YYYY-MM-DD format."
            ) from exc

    def _parse_optional_return_date(
        self, value: str | date | None, is_round_trip: bool
    ) -> date | None:
        if not is_round_trip:
            return None
        if value is None or (isinstance(value, str) and not value.strip()):
            raise SearchValidationError("Return date is required for round trips.")
        return self._parse_date(value, "Return date")

    @staticmethod
    def _parse_optional_price(value: str | Decimal | None) -> Decimal | None:
        if value is None:
            return None
        if isinstance(value, Decimal):
            return value
        clean_value = value.strip()
        if not clean_value:
            return None
        try:
            price = Decimal(clean_value)
        except InvalidOperation as exc:
            raise SearchValidationError(
                "Maximum price must be a numeric value."
            ) from exc
        if price < 0:
            raise SearchValidationError("Maximum price must not be negative.")
        return price

    @staticmethod
    def _filter_by_max_price(
        offers: list[FlightOffer], max_price: Decimal | None
    ) -> list[FlightOffer]:
        if max_price is None:
            return list(offers)
        return [offer for offer in offers if offer.price <= max_price]
