from datetime import date, datetime
from decimal import Decimal

from flight_api.semi_manual_provider import (
    SEMI_MANUAL_CLIPBOARD_PROVIDER_PREFIX,
    SemiManualSiteFlightProvider,
    is_semi_manual_source_offer,
    parse_clipboard_flight_offers,
)


def test_semi_manual_provider_opens_source_pages_as_import_targets():
    provider = SemiManualSiteFlightProvider(open_pages=False)

    offers = provider.search_flights(
        origin="STR",
        destination="LIS",
        departure_date=date(2026, 7, 10),
        return_date=None,
        max_price=None,
        currency="EUR",
    )

    assert len(offers) == 3
    assert all(is_semi_manual_source_offer(offer) for offer in offers)
    assert offers[0].airline == "Open Google Flights"
    assert offers[0].booking_url


def test_parse_clipboard_flight_offers_imports_copied_result_text():
    source_offer = SemiManualSiteFlightProvider(open_pages=False).search_flights(
        origin="STR",
        destination="LIS",
        departure_date=date(2026, 7, 10),
        return_date=None,
        max_price=None,
        currency="EUR",
    )[0]
    copied_text = """
    Lufthansa
    06:45 - 09:05
    2h 20m
    Nonstop
    €149.99

    Eurowings
    11:15 - 15:05
    3h 50m
    1 stop
    EUR 119,50
    """

    offers = parse_clipboard_flight_offers(copied_text, source_offer)

    assert [offer.airline for offer in offers] == ["Eurowings", "Lufthansa"]
    assert [offer.price for offer in offers] == [
        Decimal("119.50"),
        Decimal("149.99"),
    ]
    assert offers[0].departure_time == datetime(2026, 7, 10, 11, 15)
    assert offers[0].arrival_time == datetime(2026, 7, 10, 15, 5)
    assert offers[0].duration == "3h 50m"
    assert offers[0].number_of_stops == 1
    assert offers[0].source_provider.startswith(SEMI_MANUAL_CLIPBOARD_PROVIDER_PREFIX)


def test_parse_clipboard_flight_offers_ignores_text_without_currency_markers():
    source_offer = SemiManualSiteFlightProvider(open_pages=False).search_flights(
        origin="STR",
        destination="LIS",
        departure_date=date(2026, 7, 10),
        return_date=None,
        max_price=None,
        currency="EUR",
    )[0]

    offers = parse_clipboard_flight_offers("Lufthansa\n06:45 - 09:05\n149.99", source_offer)

    assert offers == []
