from datetime import date, datetime
from decimal import Decimal

from plotting import build_price_history_figure, create_price_history_figure
from storage import FlightSearchDatabase, PriceHistoryEntry, TrackedRoute


def make_route(route_id=1):
    return TrackedRoute(
        id=route_id,
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


def make_history(price, checked_at):
    return PriceHistoryEntry(
        id=None,
        tracked_route_id=1,
        checked_at=checked_at,
        airline="Ryanair",
        price=Decimal(price),
        currency="EUR",
        number_of_stops=0,
        departure_time=datetime(2026, 7, 10, 20, 30),
        arrival_time=datetime(2026, 7, 10, 23, 5),
        duration="2h 35m",
        source_provider="mock",
        booking_url="https://example.com/book",
    )


def test_build_price_history_figure_plots_cheapest_price_per_check():
    route = make_route()
    first_check = datetime(2026, 5, 13, 12, 30)
    second_check = datetime(2026, 5, 14, 12, 30)

    figure = build_price_history_figure(
        route,
        [
            make_history("120.00", first_check),
            make_history("100.00", first_check),
            make_history("89.99", second_check),
        ],
    )

    axis = figure.axes[0]
    price_line = axis.lines[0]
    target_line = axis.lines[1]

    assert axis.get_title() == "STR to LIS"
    assert list(price_line.get_ydata()) == [100.0, 89.99]
    assert list(target_line.get_ydata()) == [150.0, 150.0]


def test_create_price_history_figure_loads_history_from_database(tmp_path):
    database = FlightSearchDatabase(tmp_path / "flight_search.db")
    database.initialize()
    route = database.add_tracked_route(make_route(route_id=None))
    database.add_price_history_entry(
        make_history("89.99", datetime(2026, 5, 13, 12, 30))
    )

    figure = create_price_history_figure(database, route)

    assert list(figure.axes[0].lines[0].get_ydata()) == [89.99]


def test_build_price_history_figure_handles_empty_history():
    figure = build_price_history_figure(make_route(), [])

    axis = figure.axes[0]

    assert len(axis.lines) == 0
    assert axis.texts[0].get_text() == "No price history yet"
