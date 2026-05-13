"""Matplotlib price history plots for tracked routes."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from typing import Iterable

from matplotlib.figure import Figure

from storage import FlightSearchDatabase, PriceHistoryEntry, TrackedRoute


def create_price_history_figure(
    database: FlightSearchDatabase,
    route: TrackedRoute,
) -> Figure:
    if route.id is None:
        return build_price_history_figure(route, [])
    return build_price_history_figure(
        route,
        database.load_price_history(route.id),
    )


def build_price_history_figure(
    route: TrackedRoute,
    history: Iterable[PriceHistoryEntry],
) -> Figure:
    figure = Figure(figsize=(8, 4.5), dpi=100)
    axis = figure.add_subplot(111)
    axis.set_title(f"{route.origin} to {route.destination}")
    axis.set_xlabel("Check time")
    axis.set_ylabel(f"Price ({route.currency})")
    axis.grid(True, alpha=0.3)

    cheapest_points = _cheapest_price_per_check(history)
    if not cheapest_points:
        axis.text(
            0.5,
            0.5,
            "No price history yet",
            ha="center",
            va="center",
            transform=axis.transAxes,
        )
        return figure

    checked_at_values = [point[0] for point in cheapest_points]
    price_values = [float(point[1]) for point in cheapest_points]
    axis.plot(checked_at_values, price_values, marker="o", label="Cheapest")

    lowest_price = min(price_values)
    lowest_index = price_values.index(lowest_price)
    axis.scatter(
        [checked_at_values[lowest_index]],
        [lowest_price],
        color="tab:green",
        zorder=3,
        label="Lowest",
    )

    if route.max_price is not None:
        axis.axhline(
            float(route.max_price),
            color="tab:red",
            linestyle="--",
            linewidth=1,
            label="Target",
        )

    axis.legend()
    figure.autofmt_xdate()
    figure.tight_layout()
    return figure


def _cheapest_price_per_check(
    history: Iterable[PriceHistoryEntry],
) -> list[tuple[datetime, Decimal]]:
    prices_by_check = defaultdict(list)
    for entry in history:
        prices_by_check[entry.checked_at].append(entry.price)
    return [
        (checked_at, min(prices))
        for checked_at, prices in sorted(prices_by_check.items(), key=lambda item: item[0])
    ]
