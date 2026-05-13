from datetime import datetime
from decimal import Decimal

from gui.app import RESULT_COLUMNS, format_offer_row
from storage import FlightOffer


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
