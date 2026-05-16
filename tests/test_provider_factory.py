import pytest

from config import AppConfig
from flight_api import (
    AmadeusProvider,
    AutomatedSiteFlightProvider,
    BrowserAssistedFlightProvider,
    MockFlightProvider,
    MultiApiFlightProvider,
    SerpApiGoogleFlightsProvider,
)
from flight_api.provider_factory import create_flight_provider


def make_config(provider):
    return AppConfig(
        flight_api_provider=provider,
        amadeus_client_id="client-id",
        amadeus_client_secret="client-secret",
        default_currency="EUR",
        default_origin="STR",
        database_path="storage/flight_search.db",
        amadeus_base_url="https://example.test",
        request_timeout_seconds=20,
        serpapi_api_key="serp-key",
        serpapi_base_url="https://serpapi.test/search",
    )


def test_provider_factory_creates_mock_provider():
    assert isinstance(create_flight_provider(make_config("mock")), MockFlightProvider)


def test_provider_factory_creates_amadeus_provider():
    assert isinstance(create_flight_provider(make_config("amadeus")), AmadeusProvider)


def test_provider_factory_creates_serpapi_google_flights_provider():
    assert isinstance(
        create_flight_provider(make_config("serpapi_google_flights")),
        SerpApiGoogleFlightsProvider,
    )


def test_provider_factory_accepts_google_flights_alias():
    assert isinstance(
        create_flight_provider(make_config("google_flights")),
        SerpApiGoogleFlightsProvider,
    )


def test_provider_factory_creates_multi_api_provider():
    provider = create_flight_provider(make_config("multi_api"))

    assert isinstance(provider, MultiApiFlightProvider)
    assert len(provider.providers) == 2


def test_provider_factory_creates_browser_assisted_provider():
    assert isinstance(
        create_flight_provider(make_config("browser_assisted")),
        BrowserAssistedFlightProvider,
    )


def test_provider_factory_creates_automated_site_check_provider():
    assert isinstance(
        create_flight_provider(make_config("automated_site_check")),
        AutomatedSiteFlightProvider,
    )


def test_provider_factory_rejects_unknown_provider():
    with pytest.raises(ValueError, match="Unsupported"):
        create_flight_provider(make_config("unknown"))
