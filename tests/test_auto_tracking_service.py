from datetime import datetime
from decimal import Decimal

from flight_api import MockFlightProvider
from services import AutomaticTrackingService, SearchService, TrackingService
from storage import FlightSearchDatabase


def build_services(tmp_path, now):
    database = FlightSearchDatabase(tmp_path / "flight_search.db")
    database.initialize()
    search_service = SearchService(MockFlightProvider())
    tracking_service = TrackingService(database, search_service, now_provider=now)
    automatic_tracking_service = AutomaticTrackingService(tracking_service)
    return tracking_service, automatic_tracking_service


def add_route(tracking_service):
    offer = tracking_service.search_service.search(
        origin="STR",
        destination="LIS",
        departure_date="2026-07-10",
    )[0]
    return tracking_service.add_route_from_search(
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


def test_automatic_tracking_checks_due_route(tmp_path):
    now = lambda: datetime(2026, 5, 13, 12, 0)
    tracking_service, automatic_tracking_service = build_services(tmp_path, now)
    route = add_route(tracking_service)
    automatic_tracking_service.set_route_interval(route.id, "Hourly")

    results = automatic_tracking_service.run_due_checks()

    assert len(results) == 1
    assert results[0].entry.price == Decimal("89.99")
    assert tracking_service.list_route_statuses()[0].current_price == Decimal("89.99")


def test_automatic_tracking_prevents_duplicate_checks_within_interval(tmp_path):
    current_time = datetime(2026, 5, 13, 12, 0)
    tracking_service, automatic_tracking_service = build_services(
        tmp_path, lambda: current_time
    )
    route = add_route(tracking_service)
    automatic_tracking_service.set_route_interval(route.id, "Every 6 hours")
    automatic_tracking_service.run_due_checks()

    results = automatic_tracking_service.run_due_checks(
        now=datetime(2026, 5, 13, 14, 0)
    )

    assert results == []
    assert len(tracking_service.database.load_price_history(route.id)) == 1


def test_automatic_tracking_manual_routes_are_not_due(tmp_path):
    tracking_service, automatic_tracking_service = build_services(
        tmp_path, lambda: datetime(2026, 5, 13, 12, 0)
    )
    add_route(tracking_service)

    assert automatic_tracking_service.list_due_routes() == []
