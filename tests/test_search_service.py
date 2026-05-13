from datetime import date
from decimal import Decimal

import pytest

from flight_api import MockFlightProvider
from services import SearchService, SearchValidationError
from storage import FlightOffer


def test_search_returns_filtered_sorted_offers():
    service = SearchService(MockFlightProvider())

    offers = service.search(
        origin="str",
        destination="lis",
        departure_date="2026-07-10",
        max_price="140.00",
        currency="eur",
    )

    assert [offer.price for offer in offers] == [
        Decimal("89.99"),
        Decimal("119.50"),
        Decimal("137.75"),
    ]
    assert all(isinstance(offer, FlightOffer) for offer in offers)
    assert all(offer.price <= Decimal("140.00") for offer in offers)
    assert all(offer.origin == "STR" for offer in offers)
    assert all(offer.destination == "LIS" for offer in offers)
    assert all(offer.currency == "EUR" for offer in offers)


def test_search_accepts_date_and_decimal_values():
    service = SearchService(MockFlightProvider())

    offers = service.search(
        origin="STR",
        destination="LIS",
        departure_date=date(2026, 7, 10),
        max_price=Decimal("100.00"),
        currency="EUR",
    )

    assert [offer.price for offer in offers] == [Decimal("89.99")]


@pytest.mark.parametrize(
    ("origin", "destination", "message"),
    [
        ("", "LIS", "Origin must not be empty."),
        ("STR", "", "Destination must not be empty."),
    ],
)
def test_search_validates_required_airports(origin, destination, message):
    service = SearchService(MockFlightProvider())

    with pytest.raises(SearchValidationError, match=message):
        service.search(
            origin=origin,
            destination=destination,
            departure_date="2026-07-10",
        )


def test_search_validates_departure_date():
    service = SearchService(MockFlightProvider())

    with pytest.raises(SearchValidationError, match="Departure date"):
        service.search(
            origin="STR",
            destination="LIS",
            departure_date="07/10/2026",
        )


def test_search_validates_round_trip_return_date():
    service = SearchService(MockFlightProvider())

    with pytest.raises(SearchValidationError, match="Return date is required"):
        service.search(
            origin="STR",
            destination="LIS",
            departure_date="2026-07-10",
            is_round_trip=True,
        )


def test_search_validates_return_date_format():
    service = SearchService(MockFlightProvider())

    with pytest.raises(SearchValidationError, match="Return date"):
        service.search(
            origin="STR",
            destination="LIS",
            departure_date="2026-07-10",
            return_date="17/07/2026",
            is_round_trip=True,
        )


def test_search_validates_maximum_price():
    service = SearchService(MockFlightProvider())

    with pytest.raises(SearchValidationError, match="Maximum price"):
        service.search(
            origin="STR",
            destination="LIS",
            departure_date="2026-07-10",
            max_price="cheap",
        )
