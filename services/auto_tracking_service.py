"""Automatic tracking intervals and due-route checks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from storage import PriceHistoryEntry, TrackedRoute

from .tracking_service import TrackingError, TrackingService


CHECK_INTERVAL_OPTIONS: dict[str, int | None] = {
    "Manual only": None,
    "Daily": 24,
    "Every 12 hours": 12,
    "Every 6 hours": 6,
    "Hourly": 1,
}


@dataclass(frozen=True, slots=True)
class AutomaticCheckResult:
    route: TrackedRoute
    entry: PriceHistoryEntry | None
    error: str | None = None


class AutomaticTrackingService:
    def __init__(self, tracking_service: TrackingService) -> None:
        self.tracking_service = tracking_service

    def set_route_interval(self, route_id: int, label: str) -> None:
        if label not in CHECK_INTERVAL_OPTIONS:
            raise TrackingError(f"Unknown check interval: {label}")
        self.tracking_service.database.update_tracked_route_check_interval(
            route_id, CHECK_INTERVAL_OPTIONS[label]
        )

    def list_due_routes(self, now: datetime | None = None) -> list[TrackedRoute]:
        current_time = now or self.tracking_service.now_provider()
        routes = self.tracking_service.database.list_tracked_routes()
        return [route for route in routes if self._is_due(route, current_time)]

    def run_due_checks(self, now: datetime | None = None) -> list[AutomaticCheckResult]:
        results = []
        for route in self.list_due_routes(now):
            try:
                entry = self.tracking_service.check_price_now(route.id)
            except TrackingError as exc:
                results.append(AutomaticCheckResult(route=route, entry=None, error=str(exc)))
            else:
                results.append(AutomaticCheckResult(route=route, entry=entry))
        return results

    @staticmethod
    def interval_label(check_interval_hours: int | None) -> str:
        for label, hours in CHECK_INTERVAL_OPTIONS.items():
            if hours == check_interval_hours:
                return label
        return f"Every {check_interval_hours} hours"

    @staticmethod
    def _is_due(route: TrackedRoute, now: datetime) -> bool:
        if not route.active or route.check_interval_hours is None:
            return False
        if route.last_checked_at is None:
            return True
        next_due_at = route.last_checked_at + timedelta(hours=route.check_interval_hours)
        return now >= next_due_at
