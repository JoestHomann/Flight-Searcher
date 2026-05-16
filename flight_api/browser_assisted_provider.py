"""Browser-assisted provider that opens configured flight search sites."""

from __future__ import annotations

import webbrowser
from collections.abc import Callable
from datetime import date, datetime, time
from decimal import Decimal

from storage import FlightOffer

from .base_provider import FlightProvider
from .site_sources import DEFAULT_FLIGHT_SEARCH_SITES, FlightSearchSite


BROWSER_ASSISTED_PROVIDER_PREFIX = "browser_assisted:"


class BrowserAssistedFlightProvider(FlightProvider):
    """Open search pages and return source-link rows for manual comparison."""

    source_provider = "browser_assisted"

    def __init__(
        self,
        sites: tuple[FlightSearchSite, ...] = DEFAULT_FLIGHT_SEARCH_SITES,
        opener: Callable[[str], bool] | None = None,
        open_pages: bool = True,
    ) -> None:
        self.sites = sites
        self.opener = opener or webbrowser.open
        self.open_pages = open_pages

    def search_flights(
        self,
        origin: str,
        destination: str,
        departure_date: date,
        return_date: date | None,
        max_price: Decimal | None,
        currency: str,
    ) -> list[FlightOffer]:
        offers = []
        for site in self.sites:
            url = site.build_url(
                origin=origin,
                destination=destination,
                departure_date=departure_date,
                return_date=return_date,
                currency=currency,
            )
            if self.open_pages:
                self.opener(url)
            offers.append(
                self._handoff_offer(
                    site=site,
                    origin=origin,
                    destination=destination,
                    departure_date=departure_date,
                    currency=currency,
                    url=url,
                )
            )
        return offers

    @staticmethod
    def _handoff_offer(
        site: FlightSearchSite,
        origin: str,
        destination: str,
        departure_date: date,
        currency: str,
        url: str,
    ) -> FlightOffer:
        departure_at = datetime.combine(departure_date, time())
        return FlightOffer(
            airline=f"Open {site.display_name}",
            origin=origin,
            destination=destination,
            departure_time=departure_at,
            arrival_time=departure_at,
            duration="Manual check",
            number_of_stops=0,
            price=Decimal("0"),
            currency=currency,
            booking_url=url,
            source_provider=f"{BROWSER_ASSISTED_PROVIDER_PREFIX}{site.key}",
        )


def is_browser_assisted_offer(offer: FlightOffer) -> bool:
    return offer.source_provider.startswith(BROWSER_ASSISTED_PROVIDER_PREFIX)
