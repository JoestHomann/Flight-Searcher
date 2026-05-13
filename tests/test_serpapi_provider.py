from datetime import date, datetime
from decimal import Decimal

import pytest

from flight_api import (
    MissingCredentialsError,
    ProviderAuthenticationError,
    ProviderRateLimitError,
    SerpApiGoogleFlightsProvider,
)
from storage import FlightOffer


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self.payload = payload

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.get_calls = []

    def get(self, url, params, timeout):
        self.get_calls.append({"url": url, "params": params, "timeout": timeout})
        return self.response


def test_serpapi_google_flights_provider_maps_flight_results():
    session = FakeSession(
        FakeResponse(
            200,
            {
                "search_metadata": {
                    "google_flights_url": "https://www.google.com/travel/flights"
                },
                "best_flights": [
                    {
                        "flights": [
                            {
                                "departure_airport": {
                                    "id": "STR",
                                    "time": "2026-07-10 06:45",
                                },
                                "arrival_airport": {
                                    "id": "AMS",
                                    "time": "2026-07-10 08:05",
                                },
                                "duration": 80,
                                "airline": "KLM",
                            },
                            {
                                "departure_airport": {
                                    "id": "AMS",
                                    "time": "2026-07-10 09:00",
                                },
                                "arrival_airport": {
                                    "id": "LIS",
                                    "time": "2026-07-10 11:20",
                                },
                                "duration": 140,
                                "airline": "KLM",
                            },
                        ],
                        "total_duration": 275,
                        "price": 139,
                    }
                ],
            },
        )
    )
    provider = SerpApiGoogleFlightsProvider(
        api_key="serp-key",
        base_url="https://serpapi.test/search",
        timeout_seconds=8,
        session=session,
    )

    offers = provider.search_flights(
        origin="STR",
        destination="LIS",
        departure_date=date(2026, 7, 10),
        return_date=None,
        max_price=Decimal("150"),
        currency="EUR",
    )

    assert session.get_calls[0]["params"]["engine"] == "google_flights"
    assert session.get_calls[0]["params"]["type"] == 2
    assert session.get_calls[0]["params"]["max_price"] == "150"
    assert offers == [
        FlightOffer(
            airline="KLM",
            origin="STR",
            destination="LIS",
            departure_time=datetime(2026, 7, 10, 6, 45),
            arrival_time=datetime(2026, 7, 10, 11, 20),
            duration="4h 35m",
            number_of_stops=1,
            price=Decimal("139"),
            currency="EUR",
            booking_url="https://www.google.com/travel/flights",
            source_provider="serpapi_google_flights",
        )
    ]


def test_serpapi_google_flights_provider_requires_api_key():
    provider = SerpApiGoogleFlightsProvider(api_key="")

    with pytest.raises(MissingCredentialsError):
        provider.search_flights(
            origin="STR",
            destination="LIS",
            departure_date=date(2026, 7, 10),
            return_date=None,
            max_price=None,
            currency="EUR",
        )


def test_serpapi_google_flights_provider_handles_authentication_error():
    provider = SerpApiGoogleFlightsProvider(
        api_key="bad-key",
        session=FakeSession(FakeResponse(401, {"error": "invalid api key"})),
    )

    with pytest.raises(ProviderAuthenticationError):
        provider.search_flights(
            origin="STR",
            destination="LIS",
            departure_date=date(2026, 7, 10),
            return_date=None,
            max_price=None,
            currency="EUR",
        )


def test_serpapi_google_flights_provider_handles_rate_limit():
    provider = SerpApiGoogleFlightsProvider(
        api_key="serp-key",
        session=FakeSession(FakeResponse(429, {"error": "rate limit"})),
    )

    with pytest.raises(ProviderRateLimitError):
        provider.search_flights(
            origin="STR",
            destination="LIS",
            departure_date=date(2026, 7, 10),
            return_date=None,
            max_price=None,
            currency="EUR",
        )
