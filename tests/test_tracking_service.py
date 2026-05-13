from datetime import datetime
from decimal import Decimal

from flight_api import MockFlightProvider
from services import SearchService, TrackingService
from storage import FlightSearchDatabase


def build_tracking_service(tmp_path, now=None):
    database = FlightSearchDatabase(tmp_path / "flight_search.db")
    database.initialize()
    search_service = SearchService(MockFlightProvider())
    return TrackingService(
        database,
        search_service,
        now_provider=now or (lambda: datetime(2026, 5, 13, 12, 0)),
    )


def test_add_route_from_search_lists_tracked_route(tmp_path):
    service = build_tracking_service(tmp_path)
    offer = service.search_service.search(
        origin="STR",
        destination="LIS",
        departure_date="2026-07-10",
        max_price="150",
    )[0]

    route = service.add_route_from_search(
        {
            "origin": "STR",
            "destination": "LIS",
            "departure_date": "2026-07-10",
            "return_date": "",
            "is_round_trip": "False",
            "max_price": "150",
            "currency": "EUR",
        },
        offer,
    )
    statuses = service.list_route_statuses()

    assert route.id is not None
    assert len(statuses) == 1
    assert statuses[0].route.origin == "STR"
    assert statuses[0].route.destination == "LIS"
    assert statuses[0].route.max_price == Decimal("150")
    assert statuses[0].current_price is None
    assert statuses[0].lowest_price is None


def test_check_price_now_saves_history_and_updates_status(tmp_path):
    checked_at = datetime(2026, 5, 13, 12, 30)
    service = build_tracking_service(tmp_path, now=lambda: checked_at)
    offer = service.search_service.search(
        origin="STR",
        destination="LIS",
        departure_date="2026-07-10",
    )[0]
    route = service.add_route_from_search(
        {
            "origin": "STR",
            "destination": "LIS",
            "departure_date": "2026-07-10",
            "return_date": "",
            "is_round_trip": "False",
            "max_price": "",
            "currency": "EUR",
        },
        offer,
    )

    entry = service.check_price_now(route.id)
    statuses = service.list_route_statuses()

    assert entry.price == Decimal("89.99")
    assert statuses[0].current_price == Decimal("89.99")
    assert statuses[0].lowest_price == Decimal("89.99")
    assert statuses[0].route.last_checked_at == checked_at


def test_remove_route_removes_saved_route(tmp_path):
    service = build_tracking_service(tmp_path)
    offer = service.search_service.search(
        origin="STR",
        destination="LIS",
        departure_date="2026-07-10",
    )[0]
    route = service.add_route_from_search(
        {
            "origin": "STR",
            "destination": "LIS",
            "departure_date": "2026-07-10",
            "return_date": "",
            "is_round_trip": "False",
            "max_price": "",
            "currency": "EUR",
        },
        offer,
    )

    service.remove_route(route.id)

    assert service.list_route_statuses() == []
