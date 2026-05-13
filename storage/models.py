"""Shared data models for flight search, tracking, and price history."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any


@dataclass(slots=True)
class FlightOffer:
    airline: str
    origin: str
    destination: str
    departure_time: datetime
    arrival_time: datetime
    duration: str
    number_of_stops: int
    price: Decimal
    currency: str
    booking_url: str | None
    source_provider: str

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["departure_time"] = self.departure_time.isoformat()
        data["arrival_time"] = self.arrival_time.isoformat()
        data["price"] = str(self.price)
        return data


@dataclass(slots=True)
class TrackedRoute:
    id: int | None
    origin: str
    destination: str
    departure_date: date
    return_date: date | None
    is_round_trip: bool
    max_price: Decimal | None
    currency: str
    active: bool
    created_at: datetime
    last_checked_at: datetime | None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["departure_date"] = self.departure_date.isoformat()
        data["return_date"] = self.return_date.isoformat() if self.return_date else None
        data["max_price"] = str(self.max_price) if self.max_price is not None else None
        data["created_at"] = self.created_at.isoformat()
        data["last_checked_at"] = (
            self.last_checked_at.isoformat() if self.last_checked_at else None
        )
        return data


@dataclass(slots=True)
class PriceHistoryEntry:
    id: int | None
    tracked_route_id: int
    checked_at: datetime
    airline: str
    price: Decimal
    currency: str
    number_of_stops: int
    departure_time: datetime
    arrival_time: datetime
    duration: str
    source_provider: str
    booking_url: str | None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["checked_at"] = self.checked_at.isoformat()
        data["price"] = str(self.price)
        data["departure_time"] = self.departure_time.isoformat()
        data["arrival_time"] = self.arrival_time.isoformat()
        return data
