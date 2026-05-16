"""Shared site search URL builders for browser-based providers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from urllib.parse import quote_plus, urlencode


@dataclass(frozen=True, slots=True)
class FlightSearchSite:
    key: str
    display_name: str
    supports_fares: bool
    notes: str

    def build_url(
        self,
        origin: str,
        destination: str,
        departure_date: date,
        return_date: date | None,
        currency: str,
    ) -> str:
        if self.key == "google_flights":
            return _google_flights_url(origin, destination, departure_date, return_date)
        if self.key == "booking_flights":
            return _booking_flights_url(
                origin,
                destination,
                departure_date,
                return_date,
                currency,
            )
        if self.key == "flightradar24":
            return _flightradar24_url(origin, destination)
        raise ValueError(f"Unsupported flight search site: {self.key}")


DEFAULT_FLIGHT_SEARCH_SITES = (
    FlightSearchSite(
        key="google_flights",
        display_name="Google Flights",
        supports_fares=True,
        notes="Fare discovery and booking-source comparison.",
    ),
    FlightSearchSite(
        key="booking_flights",
        display_name="Booking.com Flights",
        supports_fares=True,
        notes="Booking.com flight search handoff.",
    ),
    FlightSearchSite(
        key="flightradar24",
        display_name="Flightradar24",
        supports_fares=False,
        notes="Flight status and route enrichment; not a fare source.",
    ),
)


def _google_flights_url(
    origin: str,
    destination: str,
    departure_date: date,
    return_date: date | None,
) -> str:
    query = f"Flights from {origin} to {destination} on {departure_date.isoformat()}"
    if return_date is not None:
        query = f"{query} returning {return_date.isoformat()}"
    return f"https://www.google.com/travel/flights?q={quote_plus(query)}"


def _booking_flights_url(
    origin: str,
    destination: str,
    departure_date: date,
    return_date: date | None,
    currency: str,
) -> str:
    query = f"{origin} to {destination} {departure_date.isoformat()}"
    if return_date is not None:
        query = f"{query} returning {return_date.isoformat()}"
    params = {
        "query": query,
        "currency": currency,
    }
    return f"https://www.booking.com/flights/index.html?{urlencode(params)}"


def _flightradar24_url(origin: str, destination: str) -> str:
    route = f"{origin.lower()}-{destination.lower()}"
    return f"https://www.flightradar24.com/data/flights/{route}"
