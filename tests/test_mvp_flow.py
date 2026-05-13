from datetime import datetime
from decimal import Decimal

from flight_api import MockFlightProvider
from plotting import create_price_history_figure
from services import SearchService, TrackingService
from storage import FlightSearchDatabase


def test_mock_search_tracking_history_and_plot_flow(tmp_path):
    database = FlightSearchDatabase(tmp_path / "flight_search.db")
    database.initialize()
    search_service = SearchService(MockFlightProvider())
    tracking_service = TrackingService(
        database,
        search_service,
        now_provider=lambda: datetime(2026, 5, 13, 12, 0),
    )

    offers = search_service.search(
        origin="STR",
        destination="LIS",
        departure_date="2026-07-10",
        max_price="150",
        currency="EUR",
    )
    route = tracking_service.add_route_from_search(
        {
            "origin": "STR",
            "destination": "LIS",
            "departure_date": "2026-07-10",
            "return_date": "",
            "is_round_trip": "False",
            "max_price": "150",
            "currency": "EUR",
        },
        offers[0],
    )
    entry = tracking_service.check_price_now(route.id)
    history = database.load_price_history(route.id)
    figure = create_price_history_figure(database, route)

    assert offers[0].price == Decimal("89.99")
    assert entry.price == Decimal("89.99")
    assert history == [entry]
    assert list(figure.axes[0].lines[0].get_ydata()) == [89.99]
