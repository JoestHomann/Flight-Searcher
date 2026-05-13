from datetime import date, datetime
from decimal import Decimal

from storage import (
    FlightSearchDatabase,
    PriceHistoryEntry,
    TrackedRoute,
)


def test_database_creates_tables(tmp_path):
    database_path = tmp_path / "flight_search.db"
    database = FlightSearchDatabase(database_path)

    database.initialize()

    assert database_path.exists()


def test_add_list_and_remove_tracked_route(tmp_path):
    database = FlightSearchDatabase(tmp_path / "flight_search.db")
    database.initialize()
    route = TrackedRoute(
        id=None,
        origin="STR",
        destination="LIS",
        departure_date=date(2026, 7, 10),
        return_date=None,
        is_round_trip=False,
        max_price=Decimal("160.00"),
        currency="EUR",
        active=True,
        created_at=datetime(2026, 5, 13, 12, 0),
        last_checked_at=None,
    )

    saved_route = database.add_tracked_route(route)
    routes = database.list_tracked_routes()

    assert saved_route.id is not None
    assert routes == [saved_route]

    database.remove_tracked_route(saved_route.id)

    assert database.list_tracked_routes() == []


def test_add_and_load_price_history(tmp_path):
    database = FlightSearchDatabase(tmp_path / "flight_search.db")
    database.initialize()
    route = database.add_tracked_route(
        TrackedRoute(
            id=None,
            origin="STR",
            destination="LIS",
            departure_date=date(2026, 7, 10),
            return_date=None,
            is_round_trip=False,
            max_price=Decimal("160.00"),
            currency="EUR",
            active=True,
            created_at=datetime(2026, 5, 13, 12, 0),
            last_checked_at=None,
        )
    )
    entry = PriceHistoryEntry(
        id=None,
        tracked_route_id=route.id,
        checked_at=datetime(2026, 5, 13, 12, 30),
        airline="Lufthansa",
        price=Decimal("129.99"),
        currency="EUR",
        number_of_stops=0,
        departure_time=datetime(2026, 7, 10, 8, 20),
        arrival_time=datetime(2026, 7, 10, 10, 55),
        duration="2h 35m",
        source_provider="mock",
        booking_url="https://example.com/book",
    )

    saved_entry = database.add_price_history_entry(entry)
    history = database.load_price_history(route.id)

    assert saved_entry.id is not None
    assert history == [saved_entry]
