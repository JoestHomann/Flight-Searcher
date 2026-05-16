from datetime import date, datetime
from decimal import Decimal

import pytest

from flight_api import (
    FlightProvider,
    MissingCredentialsError,
    MultiApiFlightProvider,
    ProviderResponseError,
)
from storage import FlightOffer


class StaticProvider(FlightProvider):
    def __init__(self, offers):
        self.offers = offers

    def search_flights(
        self,
        origin,
        destination,
        departure_date,
        return_date,
        max_price,
        currency,
    ):
        return self.offers


class MissingProvider(FlightProvider):
    def search_flights(
        self,
        origin,
        destination,
        departure_date,
        return_date,
        max_price,
        currency,
    ):
        raise MissingCredentialsError("Missing test credentials.")


def make_offer(price="123.45"):
    return FlightOffer(
        airline="Demo Air",
        origin="STR",
        destination="LIS",
        departure_time=datetime(2026, 7, 10, 8, 0),
        arrival_time=datetime(2026, 7, 10, 10, 0),
        duration="2h",
        number_of_stops=0,
        price=Decimal(price),
        currency="EUR",
        booking_url="https://example.test/book",
        source_provider="demo",
    )


def test_multi_api_provider_merges_and_deduplicates_configured_providers():
    offer = make_offer()
    provider = MultiApiFlightProvider(
        [
            MissingProvider(),
            StaticProvider([offer]),
            StaticProvider([offer]),
        ]
    )

    offers = provider.search_flights(
        origin="STR",
        destination="LIS",
        departure_date=date(2026, 7, 10),
        return_date=None,
        max_price=None,
        currency="EUR",
    )

    assert offers == [offer]


def test_multi_api_provider_requires_at_least_one_configured_provider():
    provider = MultiApiFlightProvider([])

    with pytest.raises(MissingCredentialsError, match="No structured API"):
        provider.search_flights(
            origin="STR",
            destination="LIS",
            departure_date=date(2026, 7, 10),
            return_date=None,
            max_price=None,
            currency="EUR",
        )


def test_multi_api_provider_reports_errors_when_every_provider_fails():
    provider = MultiApiFlightProvider([MissingProvider()])

    with pytest.raises(ProviderResponseError, match="No structured API"):
        provider.search_flights(
            origin="STR",
            destination="LIS",
            departure_date=date(2026, 7, 10),
            return_date=None,
            max_price=None,
            currency="EUR",
        )
