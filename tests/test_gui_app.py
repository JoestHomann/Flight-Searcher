from datetime import datetime
from datetime import date
from decimal import Decimal
from pathlib import Path

from config import AppConfig
from gui.app import (
    RESULT_COLUMNS,
    TRACKING_COLUMNS,
    format_offer_row,
    format_price_history_message,
    format_route_status_row,
    settings_display_rows,
)
from services import TrackedRouteStatus
from storage import FlightOffer, PriceHistoryEntry, TrackedRoute


def test_format_offer_row_matches_results_table_columns():
    offer = FlightOffer(
        airline="Lufthansa",
        origin="STR",
        destination="LIS",
        departure_time=datetime(2026, 7, 10, 6, 45),
        arrival_time=datetime(2026, 7, 10, 9, 5),
        duration="2h 20m",
        number_of_stops=0,
        price=Decimal("149.99"),
        currency="EUR",
        booking_url="https://example.com/book",
        source_provider="mock",
    )

    row = format_offer_row(offer)

    assert len(row) == len(RESULT_COLUMNS)
    assert row == (
        "Lufthansa",
        "STR",
        "LIS",
        "2026-07-10 06:45",
        "2026-07-10 09:05",
        "2h 20m",
        "0",
        "149.99",
        "EUR",
    )


def test_format_route_status_row_matches_tracking_table_columns():
    route = TrackedRoute(
        id=7,
        origin="STR",
        destination="LIS",
        departure_date=date(2026, 7, 10),
        return_date=None,
        is_round_trip=False,
        max_price=Decimal("150.00"),
        currency="EUR",
        active=True,
        created_at=datetime(2026, 5, 13, 12, 0),
        last_checked_at=datetime(2026, 5, 13, 12, 30),
    )
    status = TrackedRouteStatus(
        route=route,
        current_price=Decimal("89.99"),
        lowest_price=Decimal("79.99"),
    )

    row = format_route_status_row(status)

    assert len(row) == len(TRACKING_COLUMNS)
    assert row == (
        "7",
        "STR -> LIS",
        "2026-07-10",
        "",
        "150.00 EUR",
        "Manual only",
        "On",
        "2026-05-13 12:30",
        "89.99 EUR",
        "79.99 EUR",
    )


def test_format_price_history_message():
    entry = PriceHistoryEntry(
        id=1,
        tracked_route_id=7,
        checked_at=datetime(2026, 5, 13, 12, 30),
        airline="Ryanair",
        price=Decimal("89.99"),
        currency="EUR",
        number_of_stops=0,
        departure_time=datetime(2026, 7, 10, 20, 30),
        arrival_time=datetime(2026, 7, 10, 23, 5),
        duration="2h 35m",
        source_provider="mock",
        booking_url="https://example.com/book",
    )

    assert format_price_history_message(entry) == (
        "Current cheapest: 89.99 EUR (Ryanair)"
    )


def test_settings_display_rows_hides_secret_values():
    config = AppConfig(
        flight_api_provider="amadeus",
        amadeus_client_id="client-id",
        amadeus_client_secret="client-secret",
        default_currency="EUR",
        default_origin="STR",
        database_path=Path("storage/flight_search.db"),
        amadeus_base_url="https://test.api.amadeus.com",
        request_timeout_seconds=20,
        serpapi_api_key="serp-key",
        serpapi_base_url="https://serpapi.com/search",
    )

    rows = dict(settings_display_rows(config))

    assert rows["Flight API Provider"] == "amadeus"
    assert rows["Amadeus Credentials"] == "Configured"
    assert rows["SerpApi Credentials"] == "Configured"
    assert "client-secret" not in rows.values()
