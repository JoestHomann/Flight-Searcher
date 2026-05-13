"""CSV export helpers."""

from __future__ import annotations

import csv
from pathlib import Path

from storage import FlightSearchDatabase


PRICE_HISTORY_COLUMNS = (
    "checked_at",
    "airline",
    "price",
    "currency",
    "number_of_stops",
    "departure_time",
    "arrival_time",
    "duration",
    "source_provider",
    "booking_url",
)


def export_price_history_to_csv(
    database: FlightSearchDatabase,
    tracked_route_id: int,
    output_path: str | Path,
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    history = database.load_price_history(tracked_route_id)

    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(PRICE_HISTORY_COLUMNS)
        for entry in history:
            writer.writerow(
                (
                    entry.checked_at.isoformat(),
                    entry.airline,
                    str(entry.price),
                    entry.currency,
                    entry.number_of_stops,
                    entry.departure_time.isoformat(),
                    entry.arrival_time.isoformat(),
                    entry.duration,
                    entry.source_provider,
                    entry.booking_url or "",
                )
            )
    return path
