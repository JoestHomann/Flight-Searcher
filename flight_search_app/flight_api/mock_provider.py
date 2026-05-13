"""Deterministic mock flight provider for local development."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal

from flight_search_app.storage import FlightOffer

from .base_provider import FlightProvider


class MockFlightProvider(FlightProvider):
    source_provider = "mock"

    def search_flights(
        self,
        origin: str,
        destination: str,
        departure_date: date,
        return_date: date | None,
        max_price: Decimal | None,
        currency: str,
    ) -> list[FlightOffer]:
        origin_code = origin.strip().upper()
        destination_code = destination.strip().upper()
        currency_code = currency.strip().upper() or "EUR"

        offers = [
            self._build_offer(
                airline="Lufthansa",
                origin=origin_code,
                destination=destination_code,
                departure_date=departure_date,
                departure_time=time(6, 45),
                duration_hours=2,
                duration_minutes=20,
                number_of_stops=0,
                price=Decimal("149.99"),
                currency=currency_code,
                booking_id="LH-early-direct",
            ),
            self._build_offer(
                airline="Eurowings",
                origin=origin_code,
                destination=destination_code,
                departure_date=departure_date,
                departure_time=time(11, 15),
                duration_hours=3,
                duration_minutes=50,
                number_of_stops=1,
                price=Decimal("119.50"),
                currency=currency_code,
                booking_id="EW-midday-one-stop",
            ),
            self._build_offer(
                airline="KLM",
                origin=origin_code,
                destination=destination_code,
                departure_date=departure_date,
                departure_time=time(16, 5),
                duration_hours=4,
                duration_minutes=15,
                number_of_stops=1,
                price=Decimal("137.75"),
                currency=currency_code,
                booking_id="KL-afternoon-one-stop",
            ),
            self._build_offer(
                airline="Ryanair",
                origin=origin_code,
                destination=destination_code,
                departure_date=departure_date,
                departure_time=time(20, 30),
                duration_hours=2,
                duration_minutes=35,
                number_of_stops=0,
                price=Decimal("89.99"),
                currency=currency_code,
                booking_id="FR-evening-direct",
            ),
        ]

        if return_date is not None:
            offers.append(
                self._build_offer(
                    airline="Air France",
                    origin=origin_code,
                    destination=destination_code,
                    departure_date=departure_date,
                    departure_time=time(9, 20),
                    duration_hours=5,
                    duration_minutes=5,
                    number_of_stops=2,
                    price=Decimal("174.20"),
                    currency=currency_code,
                    booking_id="AF-round-trip-flex",
                )
            )

        return offers

    def _build_offer(
        self,
        airline: str,
        origin: str,
        destination: str,
        departure_date: date,
        departure_time: time,
        duration_hours: int,
        duration_minutes: int,
        number_of_stops: int,
        price: Decimal,
        currency: str,
        booking_id: str,
    ) -> FlightOffer:
        departure_at = datetime.combine(departure_date, departure_time)
        arrival_at = departure_at + timedelta(
            hours=duration_hours, minutes=duration_minutes
        )
        return FlightOffer(
            airline=airline,
            origin=origin,
            destination=destination,
            departure_time=departure_at,
            arrival_time=arrival_at,
            duration=f"{duration_hours}h {duration_minutes}m",
            number_of_stops=number_of_stops,
            price=price,
            currency=currency,
            booking_url=f"https://example.com/flights/{booking_id}",
            source_provider=self.source_provider,
        )
