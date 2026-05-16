from datetime import date
from decimal import Decimal

from flight_api.browser_assisted_provider import (
    BROWSER_ASSISTED_PROVIDER_PREFIX,
    BrowserAssistedFlightProvider,
    is_browser_assisted_offer,
)


def test_browser_assisted_provider_opens_all_source_pages_and_returns_link_rows():
    opened_urls = []
    provider = BrowserAssistedFlightProvider(
        opener=lambda url: opened_urls.append(url) or True
    )

    offers = provider.search_flights(
        origin="STR",
        destination="LIS",
        departure_date=date(2026, 7, 10),
        return_date=None,
        max_price=None,
        currency="EUR",
    )

    assert len(offers) == 3
    assert opened_urls == [offer.booking_url for offer in offers]
    assert all(offer.price == Decimal("0") for offer in offers)
    assert all(offer.source_provider.startswith(BROWSER_ASSISTED_PROVIDER_PREFIX) for offer in offers)
    assert all(is_browser_assisted_offer(offer) for offer in offers)
    assert "google.com/travel/flights" in opened_urls[0]
    assert "booking.com/flights" in opened_urls[1]
    assert "flightradar24.com" in opened_urls[2]


def test_browser_assisted_provider_can_build_links_without_opening_pages():
    provider = BrowserAssistedFlightProvider(open_pages=False)

    offers = provider.search_flights(
        origin="STR",
        destination="LIS",
        departure_date=date(2026, 7, 10),
        return_date=date(2026, 7, 17),
        max_price=None,
        currency="EUR",
    )

    assert len(offers) == 3
    assert all(offer.booking_url for offer in offers)
