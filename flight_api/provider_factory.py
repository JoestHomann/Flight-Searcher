"""Provider selection based on application configuration."""

from __future__ import annotations

from config import AppConfig

from .amadeus_provider import AmadeusProvider
from .base_provider import FlightProvider
from .mock_provider import MockFlightProvider


def create_flight_provider(config: AppConfig) -> FlightProvider:
    provider_name = config.flight_api_provider.strip().lower()
    if provider_name == "mock":
        return MockFlightProvider()
    if provider_name == "amadeus":
        return AmadeusProvider(
            client_id=config.amadeus_client_id,
            client_secret=config.amadeus_client_secret,
            base_url=config.amadeus_base_url,
            timeout_seconds=config.request_timeout_seconds,
        )
    raise ValueError(f"Unsupported flight API provider: {config.flight_api_provider}")
