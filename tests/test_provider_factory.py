import pytest

from config import AppConfig
from flight_api import AmadeusProvider, MockFlightProvider
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
    )


def test_provider_factory_creates_mock_provider():
    assert isinstance(create_flight_provider(make_config("mock")), MockFlightProvider)


def test_provider_factory_creates_amadeus_provider():
    assert isinstance(create_flight_provider(make_config("amadeus")), AmadeusProvider)


def test_provider_factory_rejects_unknown_provider():
    with pytest.raises(ValueError, match="Unsupported"):
        create_flight_provider(make_config("unknown"))
