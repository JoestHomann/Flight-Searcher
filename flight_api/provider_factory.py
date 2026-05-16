"""Provider selection based on application configuration."""

from __future__ import annotations

from config import AppConfig

from .amadeus_provider import AmadeusProvider
from .automated_site_provider import AutomatedSiteFlightProvider
from .base_provider import FlightProvider
from .browser_assisted_provider import BrowserAssistedFlightProvider
from .mock_provider import MockFlightProvider
from .multi_api_provider import MultiApiFlightProvider
from .semi_manual_provider import SemiManualSiteFlightProvider
from .serpapi_provider import SerpApiGoogleFlightsProvider


SUPPORTED_PROVIDERS = (
    "mock",
    "amadeus",
    "serpapi_google_flights",
    "multi_api",
    "browser_assisted",
    "semi_manual_site_check",
)


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
    if provider_name in {"serpapi_google_flights", "google_flights"}:
        return SerpApiGoogleFlightsProvider(
            api_key=config.serpapi_api_key,
            base_url=config.serpapi_base_url,
            timeout_seconds=config.request_timeout_seconds,
        )
    if provider_name in {"multi_api", "api_aggregate", "official_api_aggregate"}:
        return MultiApiFlightProvider(_configured_structured_providers(config))
    if provider_name in {"browser_assisted", "site_browser_assisted"}:
        return BrowserAssistedFlightProvider()
    if provider_name in {
        "semi_manual_site_check",
        "automated_site_check",
        "browser_automation",
    }:
        return SemiManualSiteFlightProvider()
    if provider_name in {"json_ld_site_check", "site_automation"}:
        return AutomatedSiteFlightProvider(
            timeout_seconds=config.request_timeout_seconds,
        )
    raise ValueError(f"Unsupported flight API provider: {config.flight_api_provider}")


def _configured_structured_providers(config: AppConfig) -> list[FlightProvider]:
    providers: list[FlightProvider] = []
    if config.amadeus_credentials_configured:
        providers.append(
            AmadeusProvider(
                client_id=config.amadeus_client_id,
                client_secret=config.amadeus_client_secret,
                base_url=config.amadeus_base_url,
                timeout_seconds=config.request_timeout_seconds,
            )
        )
    if config.serpapi_credentials_configured:
        providers.append(
            SerpApiGoogleFlightsProvider(
                api_key=config.serpapi_api_key,
                base_url=config.serpapi_base_url,
                timeout_seconds=config.request_timeout_seconds,
            )
        )
    return providers
