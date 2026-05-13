from datetime import date
from decimal import Decimal

from flight_api import FlightProvider, MockFlightProvider


def test_mock_provider_returns_realistic_offers():
    provider = MockFlightProvider()

    offers = provider.search_flights(
        origin="str",
        destination="lis",
        departure_date=date(2026, 7, 10),
        return_date=None,
        max_price=Decimal("150.00"),
        currency="eur",
    )

    assert isinstance(provider, FlightProvider)
    assert len(offers) >= 4
    assert {offer.airline for offer in offers} >= {
        "Lufthansa",
        "Eurowings",
        "KLM",
        "Ryanair",
    }
    assert {offer.number_of_stops for offer in offers} >= {0, 1}
    assert len({offer.price for offer in offers}) >= 4
    assert len({offer.departure_time.time() for offer in offers}) >= 4
    assert all(offer.origin == "STR" for offer in offers)
    assert all(offer.destination == "LIS" for offer in offers)
    assert all(offer.currency == "EUR" for offer in offers)
    assert all(offer.source_provider == "mock" for offer in offers)


def test_mock_provider_includes_extra_option_for_round_trip():
    provider = MockFlightProvider()

    offers = provider.search_flights(
        origin="STR",
        destination="LIS",
        departure_date=date(2026, 7, 10),
        return_date=date(2026, 7, 17),
        max_price=None,
        currency="EUR",
    )

    assert len(offers) == 5
    assert any(offer.number_of_stops == 2 for offer in offers)
