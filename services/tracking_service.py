"""Route tracking workflows backed by local storage."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from services.search_service import SearchService
from storage import FlightOffer, FlightSearchDatabase, PriceHistoryEntry, TrackedRoute


class TrackingError(ValueError):
    """Raised when a tracked route operation cannot be completed."""


@dataclass(slots=True)
class TrackedRouteStatus:
    route: TrackedRoute
    current_price: Decimal | None
    lowest_price: Decimal | None


class TrackingService:
    def __init__(
        self,
        database: FlightSearchDatabase,
        search_service: SearchService,
        now_provider: Callable[[], datetime] = datetime.now,
    ) -> None:
        self.database = database
        self.search_service = search_service
        self.now_provider = now_provider

    def add_route_from_search(
        self, search_values: dict[str, str], selected_offer: FlightOffer
    ) -> TrackedRoute:
        route = TrackedRoute(
            id=None,
            origin=(search_values.get("origin") or selected_offer.origin).upper(),
            destination=(
                search_values.get("destination") or selected_offer.destination
            ).upper(),
            departure_date=self._parse_date(
                search_values.get("departure_date")
                or selected_offer.departure_time.date().isoformat(),
                "Departure date",
            ),
            return_date=self._parse_optional_date(search_values.get("return_date")),
            is_round_trip=search_values.get("is_round_trip") == "True",
            max_price=self._parse_optional_price(search_values.get("max_price")),
            currency=(search_values.get("currency") or selected_offer.currency).upper(),
            active=True,
            created_at=self.now_provider(),
            last_checked_at=None,
        )
        return self.database.add_tracked_route(route)

    def remove_route(self, route_id: int) -> None:
        self.database.remove_tracked_route(route_id)

    def list_route_statuses(self) -> list[TrackedRouteStatus]:
        statuses = []
        for route in self.database.list_tracked_routes():
            history = self.database.load_price_history(route.id)
            prices = [entry.price for entry in history]
            statuses.append(
                TrackedRouteStatus(
                    route=route,
                    current_price=history[-1].price if history else None,
                    lowest_price=min(prices) if prices else None,
                )
            )
        return statuses

    def check_price_now(self, route_id: int) -> PriceHistoryEntry:
        route = self.database.get_tracked_route(route_id)
        if route is None:
            raise TrackingError("Tracked route was not found.")

        offers = self.search_service.search(
            origin=route.origin,
            destination=route.destination,
            departure_date=route.departure_date,
            return_date=route.return_date,
            is_round_trip=route.is_round_trip,
            max_price=None,
            currency=route.currency,
        )
        if not offers:
            raise TrackingError("No flights found for this tracked route.")

        cheapest_offer = min(offers, key=lambda offer: offer.price)
        checked_at = self.now_provider()
        entry = self.database.add_price_history_entry(
            PriceHistoryEntry(
                id=None,
                tracked_route_id=route.id,
                checked_at=checked_at,
                airline=cheapest_offer.airline,
                price=cheapest_offer.price,
                currency=cheapest_offer.currency,
                number_of_stops=cheapest_offer.number_of_stops,
                departure_time=cheapest_offer.departure_time,
                arrival_time=cheapest_offer.arrival_time,
                duration=cheapest_offer.duration,
                source_provider=cheapest_offer.source_provider,
                booking_url=cheapest_offer.booking_url,
            )
        )
        self.database.update_tracked_route_last_checked(route.id, checked_at)
        return entry

    @staticmethod
    def _parse_date(value: str | date, field_name: str) -> date:
        if isinstance(value, date):
            return value
        try:
            return date.fromisoformat(value.strip())
        except (AttributeError, ValueError) as exc:
            raise TrackingError(f"{field_name} must use YYYY-MM-DD format.") from exc

    def _parse_optional_date(self, value: str | None) -> date | None:
        if value is None or not value.strip():
            return None
        return self._parse_date(value, "Return date")

    @staticmethod
    def _parse_optional_price(value: str | None) -> Decimal | None:
        if value is None or not value.strip():
            return None
        try:
            return Decimal(value.strip())
        except InvalidOperation as exc:
            raise TrackingError("Maximum price must be a numeric value.") from exc
