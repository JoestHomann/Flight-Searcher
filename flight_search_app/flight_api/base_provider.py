"""Common interface for flight search providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from decimal import Decimal

from flight_search_app.storage import FlightOffer


class FlightProvider(ABC):
    @abstractmethod
    def search_flights(
        self,
        origin: str,
        destination: str,
        departure_date: date,
        return_date: date | None,
        max_price: Decimal | None,
        currency: str,
    ) -> list[FlightOffer]:
        """Return matching flight offers from a provider."""
