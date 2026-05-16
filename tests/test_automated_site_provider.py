from datetime import date, datetime
from decimal import Decimal

import pytest

from flight_api import AutomatedSiteFlightProvider, ProviderResponseError
from flight_api.automated_site_provider import AUTOMATED_SITE_PROVIDER_PREFIX
from flight_api.site_sources import DEFAULT_FLIGHT_SEARCH_SITES


JSON_LD_FLIGHT_PAGE = """
<html>
  <head>
    <script type="application/ld+json">
      {
        "@context": "https://schema.org",
        "@type": "Flight",
        "name": "Demo Air STR-LIS",
        "airline": {"name": "Demo Air"},
        "departureAirport": {"iataCode": "STR"},
        "arrivalAirport": {"iataCode": "LIS"},
        "departureTime": "2026-07-10T08:00:00",
        "arrivalTime": "2026-07-10T10:30:00",
        "offers": {
          "@type": "Offer",
          "price": "123.45",
          "priceCurrency": "EUR",
          "url": "https://example.test/book"
        }
      }
    </script>
  </head>
</html>
"""


def test_automated_site_provider_maps_machine_readable_flight_offers():
    provider = AutomatedSiteFlightProvider(
        sites=(DEFAULT_FLIGHT_SEARCH_SITES[0],),
        page_fetcher=lambda _url: JSON_LD_FLIGHT_PAGE,
    )

    offers = provider.search_flights(
        origin="STR",
        destination="LIS",
        departure_date=date(2026, 7, 10),
        return_date=None,
        max_price=None,
        currency="EUR",
    )

    assert len(offers) == 1
    offer = offers[0]
    assert offer.airline == "Demo Air"
    assert offer.origin == "STR"
    assert offer.destination == "LIS"
    assert offer.departure_time == datetime(2026, 7, 10, 8, 0)
    assert offer.arrival_time == datetime(2026, 7, 10, 10, 30)
    assert offer.duration == "2h 30m"
    assert offer.price == Decimal("123.45")
    assert offer.currency == "EUR"
    assert offer.booking_url == "https://example.test/book"
    assert offer.source_provider.startswith(AUTOMATED_SITE_PROVIDER_PREFIX)


def test_automated_site_provider_returns_no_offers_when_no_public_prices_exist():
    provider = AutomatedSiteFlightProvider(
        sites=(DEFAULT_FLIGHT_SEARCH_SITES[0],),
        page_fetcher=lambda _url: "<html>No machine-readable fares</html>",
    )

    offers = provider.search_flights(
        origin="STR",
        destination="LIS",
        departure_date=date(2026, 7, 10),
        return_date=None,
        max_price=None,
        currency="EUR",
    )

    assert offers == []


def test_automated_site_provider_reports_blocked_pages():
    provider = AutomatedSiteFlightProvider(
        sites=(DEFAULT_FLIGHT_SEARCH_SITES[0],),
        page_fetcher=lambda _url: "<html>Verify you are human</html>",
    )

    with pytest.raises(ProviderResponseError, match="human-verification"):
        provider.search_flights(
            origin="STR",
            destination="LIS",
            departure_date=date(2026, 7, 10),
            return_date=None,
            max_price=None,
            currency="EUR",
        )
