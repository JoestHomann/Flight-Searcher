from datetime import date, datetime
from decimal import Decimal

from services import NotificationService
from storage import FlightSearchDatabase, PriceHistoryEntry, TrackedRoute


def add_route(database, max_price=Decimal("150.00")):
    return database.add_tracked_route(
        TrackedRoute(
            id=None,
            origin="STR",
            destination="LIS",
            departure_date=date(2026, 7, 10),
            return_date=None,
            is_round_trip=False,
            max_price=max_price,
            currency="EUR",
            active=True,
            created_at=datetime(2026, 5, 13, 12, 0),
            last_checked_at=None,
        )
    )


def make_entry(route_id, price=Decimal("89.99"), checked_at=None):
    return PriceHistoryEntry(
        id=None,
        tracked_route_id=route_id,
        checked_at=checked_at or datetime(2026, 5, 13, 12, 30),
        airline="Ryanair",
        price=price,
        currency="EUR",
        number_of_stops=0,
        departure_time=datetime(2026, 7, 10, 20, 30),
        arrival_time=datetime(2026, 7, 10, 23, 5),
        duration="2h 35m",
        source_provider="mock",
        booking_url="https://example.com/book",
    )


def test_notification_created_when_price_is_below_target(tmp_path):
    database = FlightSearchDatabase(tmp_path / "flight_search.db")
    database.initialize()
    route = add_route(database)
    entry = database.add_price_history_entry(make_entry(route.id))
    service = NotificationService(database)

    notification = service.notification_for_entry(entry)

    assert notification is not None
    assert "below your target" in notification.message
    assert database.get_tracked_route(route.id).last_notified_at == entry.checked_at


def test_notification_respects_disabled_route_setting(tmp_path):
    database = FlightSearchDatabase(tmp_path / "flight_search.db")
    database.initialize()
    route = add_route(database)
    database.update_tracked_route_notification_enabled(route.id, False)
    entry = database.add_price_history_entry(make_entry(route.id))
    service = NotificationService(database)

    assert service.notification_for_entry(entry) is None


def test_notification_cooldown_prevents_spam(tmp_path):
    database = FlightSearchDatabase(tmp_path / "flight_search.db")
    database.initialize()
    route = add_route(database)
    first_entry = database.add_price_history_entry(
        make_entry(route.id, checked_at=datetime(2026, 5, 13, 12, 30))
    )
    second_entry = database.add_price_history_entry(
        make_entry(route.id, checked_at=datetime(2026, 5, 13, 13, 0))
    )
    service = NotificationService(database)

    assert service.notification_for_entry(first_entry) is not None
    assert service.notification_for_entry(second_entry) is None
