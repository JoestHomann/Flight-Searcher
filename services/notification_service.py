"""Target-price notifications for tracked routes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from storage import FlightSearchDatabase, PriceHistoryEntry, TrackedRoute


@dataclass(frozen=True, slots=True)
class PriceNotification:
    route: TrackedRoute
    entry: PriceHistoryEntry
    message: str


class NotificationService:
    def __init__(
        self,
        database: FlightSearchDatabase,
        cooldown: timedelta = timedelta(hours=24),
    ) -> None:
        self.database = database
        self.cooldown = cooldown

    def set_route_notifications_enabled(self, route_id: int, enabled: bool) -> None:
        self.database.update_tracked_route_notification_enabled(route_id, enabled)

    def notification_for_entry(
        self, entry: PriceHistoryEntry
    ) -> PriceNotification | None:
        route = self.database.get_tracked_route(entry.tracked_route_id)
        if route is None:
            return None
        if not self._should_notify(route, entry):
            return None

        self.database.update_tracked_route_last_notified(route.id, entry.checked_at)
        route = self.database.get_tracked_route(route.id) or route
        return PriceNotification(
            route=route,
            entry=entry,
            message=(
                f"{route.origin} to {route.destination} is now "
                f"{entry.price:.2f} {entry.currency}, below your target of "
                f"{route.max_price:.2f} {route.currency}."
            ),
        )

    def _should_notify(
        self, route: TrackedRoute, entry: PriceHistoryEntry
    ) -> bool:
        if route.id is None:
            return False
        if not route.notification_enabled:
            return False
        if route.max_price is None:
            return False
        if entry.price > route.max_price:
            return False
        if route.last_notified_at is None:
            return True
        return entry.checked_at - route.last_notified_at >= self.cooldown
