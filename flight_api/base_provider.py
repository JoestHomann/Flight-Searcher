"""Common interface for flight search providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from decimal import Decimal

from storage import FlightOffer


class FlightProviderError(RuntimeError):
    """Base error raised for provider failures that can be shown to users."""


class MissingCredentialsError(FlightProviderError):
    """Raised when a configured provider needs credentials but none exist."""


class ProviderAuthenticationError(FlightProviderError):
    """Raised when provider credentials are rejected."""


class ProviderRateLimitError(FlightProviderError):
    """Raised when the provider rate limit is reached."""


class ProviderNetworkError(FlightProviderError):
    """Raised when the provider cannot be reached."""


class ProviderResponseError(FlightProviderError):
    """Raised when the provider response cannot be parsed safely."""


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
