"""SQLite storage layer for tracked routes and price history."""

from __future__ import annotations

import sqlite3
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from .models import PriceHistoryEntry, TrackedRoute


class FlightSearchDatabase:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)

    def initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS tracked_routes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    origin TEXT NOT NULL,
                    destination TEXT NOT NULL,
                    departure_date TEXT NOT NULL,
                    return_date TEXT,
                    is_round_trip INTEGER NOT NULL,
                    max_price TEXT,
                    currency TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    last_checked_at TEXT,
                    check_interval_hours INTEGER,
                    notification_enabled INTEGER NOT NULL DEFAULT 1,
                    last_notified_at TEXT
                );

                CREATE TABLE IF NOT EXISTS price_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tracked_route_id INTEGER NOT NULL,
                    checked_at TEXT NOT NULL,
                    airline TEXT NOT NULL,
                    price TEXT NOT NULL,
                    currency TEXT NOT NULL,
                    number_of_stops INTEGER NOT NULL,
                    departure_time TEXT NOT NULL,
                    arrival_time TEXT NOT NULL,
                    duration TEXT NOT NULL,
                    source_provider TEXT NOT NULL,
                    booking_url TEXT,
                    FOREIGN KEY (tracked_route_id)
                        REFERENCES tracked_routes (id)
                        ON DELETE CASCADE
                );
                """
            )
            self._migrate_schema(connection)

    def add_tracked_route(self, route: TrackedRoute) -> TrackedRoute:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO tracked_routes (
                    origin,
                    destination,
                    departure_date,
                    return_date,
                    is_round_trip,
                    max_price,
                    currency,
                    active,
                    created_at,
                    last_checked_at,
                    check_interval_hours,
                    notification_enabled,
                    last_notified_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    route.origin,
                    route.destination,
                    route.departure_date.isoformat(),
                    route.return_date.isoformat() if route.return_date else None,
                    int(route.is_round_trip),
                    str(route.max_price) if route.max_price is not None else None,
                    route.currency,
                    int(route.active),
                    route.created_at.isoformat(),
                    route.last_checked_at.isoformat() if route.last_checked_at else None,
                    route.check_interval_hours,
                    int(route.notification_enabled),
                    route.last_notified_at.isoformat() if route.last_notified_at else None,
                ),
            )
            route_id = int(cursor.lastrowid)
        return TrackedRoute(
            id=route_id,
            origin=route.origin,
            destination=route.destination,
            departure_date=route.departure_date,
            return_date=route.return_date,
            is_round_trip=route.is_round_trip,
            max_price=route.max_price,
            currency=route.currency,
            active=route.active,
            created_at=route.created_at,
            last_checked_at=route.last_checked_at,
            check_interval_hours=route.check_interval_hours,
            notification_enabled=route.notification_enabled,
            last_notified_at=route.last_notified_at,
        )

    def remove_tracked_route(self, route_id: int) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM tracked_routes WHERE id = ?", (route_id,))

    def get_tracked_route(self, route_id: int) -> TrackedRoute | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM tracked_routes WHERE id = ?", (route_id,)
            ).fetchone()
        if row is None:
            return None
        return self._tracked_route_from_row(row)

    def list_tracked_routes(self) -> list[TrackedRoute]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM tracked_routes ORDER BY created_at DESC, id DESC"
            ).fetchall()
        return [self._tracked_route_from_row(row) for row in rows]

    def update_tracked_route_last_checked(
        self, route_id: int, checked_at: datetime
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE tracked_routes
                SET last_checked_at = ?
                WHERE id = ?
                """,
                (checked_at.isoformat(), route_id),
            )

    def update_tracked_route_check_interval(
        self, route_id: int, check_interval_hours: int | None
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE tracked_routes
                SET check_interval_hours = ?
                WHERE id = ?
                """,
                (check_interval_hours, route_id),
            )

    def update_tracked_route_notification_enabled(
        self, route_id: int, enabled: bool
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE tracked_routes
                SET notification_enabled = ?
                WHERE id = ?
                """,
                (int(enabled), route_id),
            )

    def update_tracked_route_last_notified(
        self, route_id: int, notified_at: datetime
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE tracked_routes
                SET last_notified_at = ?
                WHERE id = ?
                """,
                (notified_at.isoformat(), route_id),
            )

    def add_price_history_entry(
        self, entry: PriceHistoryEntry
    ) -> PriceHistoryEntry:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO price_history (
                    tracked_route_id,
                    checked_at,
                    airline,
                    price,
                    currency,
                    number_of_stops,
                    departure_time,
                    arrival_time,
                    duration,
                    source_provider,
                    booking_url
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.tracked_route_id,
                    entry.checked_at.isoformat(),
                    entry.airline,
                    str(entry.price),
                    entry.currency,
                    entry.number_of_stops,
                    entry.departure_time.isoformat(),
                    entry.arrival_time.isoformat(),
                    entry.duration,
                    entry.source_provider,
                    entry.booking_url,
                ),
            )
            entry_id = int(cursor.lastrowid)
        return PriceHistoryEntry(
            id=entry_id,
            tracked_route_id=entry.tracked_route_id,
            checked_at=entry.checked_at,
            airline=entry.airline,
            price=entry.price,
            currency=entry.currency,
            number_of_stops=entry.number_of_stops,
            departure_time=entry.departure_time,
            arrival_time=entry.arrival_time,
            duration=entry.duration,
            source_provider=entry.source_provider,
            booking_url=entry.booking_url,
        )

    def load_price_history(self, tracked_route_id: int) -> list[PriceHistoryEntry]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM price_history
                WHERE tracked_route_id = ?
                ORDER BY checked_at ASC, id ASC
                """,
                (tracked_route_id,),
            ).fetchall()
        return [self._price_history_entry_from_row(row) for row in rows]

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @staticmethod
    def _migrate_schema(connection: sqlite3.Connection) -> None:
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(tracked_routes)").fetchall()
        }
        if "check_interval_hours" not in columns:
            connection.execute(
                "ALTER TABLE tracked_routes ADD COLUMN check_interval_hours INTEGER"
            )
        if "notification_enabled" not in columns:
            connection.execute(
                "ALTER TABLE tracked_routes ADD COLUMN notification_enabled INTEGER NOT NULL DEFAULT 1"
            )
        if "last_notified_at" not in columns:
            connection.execute(
                "ALTER TABLE tracked_routes ADD COLUMN last_notified_at TEXT"
            )

    @staticmethod
    def _tracked_route_from_row(row: sqlite3.Row) -> TrackedRoute:
        return TrackedRoute(
            id=row["id"],
            origin=row["origin"],
            destination=row["destination"],
            departure_date=date.fromisoformat(row["departure_date"]),
            return_date=(
                date.fromisoformat(row["return_date"]) if row["return_date"] else None
            ),
            is_round_trip=bool(row["is_round_trip"]),
            max_price=Decimal(row["max_price"]) if row["max_price"] else None,
            currency=row["currency"],
            active=bool(row["active"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            last_checked_at=(
                datetime.fromisoformat(row["last_checked_at"])
                if row["last_checked_at"]
                else None
            ),
            check_interval_hours=row["check_interval_hours"],
            notification_enabled=bool(row["notification_enabled"]),
            last_notified_at=(
                datetime.fromisoformat(row["last_notified_at"])
                if row["last_notified_at"]
                else None
            ),
        )

    @staticmethod
    def _price_history_entry_from_row(row: sqlite3.Row) -> PriceHistoryEntry:
        return PriceHistoryEntry(
            id=row["id"],
            tracked_route_id=row["tracked_route_id"],
            checked_at=datetime.fromisoformat(row["checked_at"]),
            airline=row["airline"],
            price=Decimal(row["price"]),
            currency=row["currency"],
            number_of_stops=row["number_of_stops"],
            departure_time=datetime.fromisoformat(row["departure_time"]),
            arrival_time=datetime.fromisoformat(row["arrival_time"]),
            duration=row["duration"],
            source_provider=row["source_provider"],
            booking_url=row["booking_url"],
        )


def initialize_database(database_path: str | Path) -> FlightSearchDatabase:
    database = FlightSearchDatabase(database_path)
    database.initialize()
    return database
