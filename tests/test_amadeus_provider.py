from datetime import date, datetime
from decimal import Decimal

import pytest

from flight_api import (
    AmadeusProvider,
    MissingCredentialsError,
    ProviderAuthenticationError,
    ProviderRateLimitError,
)
from storage import FlightOffer


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self.payload = payload

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, token_response, search_response):
        self.token_response = token_response
        self.search_response = search_response
        self.post_calls = []
        self.get_calls = []

    def post(self, url, timeout, **kwargs):
        self.post_calls.append({"url": url, "timeout": timeout, **kwargs})
        return self.token_response

    def get(self, url, timeout, **kwargs):
        self.get_calls.append({"url": url, "timeout": timeout, **kwargs})
        return self.search_response


def test_amadeus_provider_maps_flight_offers():
    session = FakeSession(
        token_response=FakeResponse(200, {"access_token": "token", "expires_in": 1799}),
        search_response=FakeResponse(
            200,
            {
                "data": [
                    {
                        "itineraries": [
                            {
                                "duration": "PT2H20M",
                                "segments": [
                                    {
                                        "carrierCode": "LH",
                                        "departure": {
                                            "iataCode": "STR",
                                            "at": "2026-07-10T06:45:00",
                                        },
                                        "arrival": {
                                            "iataCode": "FRA",
                                            "at": "2026-07-10T07:30:00",
                                        },
                                    },
                                    {
                                        "carrierCode": "LH",
                                        "departure": {
                                            "iataCode": "FRA",
                                            "at": "2026-07-10T08:00:00",
                                        },
                                        "arrival": {
                                            "iataCode": "LIS",
                                            "at": "2026-07-10T09:05:00",
                                        },
                                    },
                                ],
                            }
                        ],
                        "price": {"grandTotal": "149.99", "currency": "EUR"},
                        "validatingAirlineCodes": ["LH"],
                    }
                ],
                "dictionaries": {"carriers": {"LH": "Lufthansa"}},
            },
        ),
    )
    provider = AmadeusProvider(
        client_id="client-id",
        client_secret="client-secret",
        base_url="https://amadeus.test",
        timeout_seconds=5,
        session=session,
    )

    offers = provider.search_flights(
        origin="STR",
        destination="LIS",
        departure_date=date(2026, 7, 10),
        return_date=None,
        max_price=Decimal("150.00"),
        currency="EUR",
    )

    assert session.post_calls[0]["data"]["grant_type"] == "client_credentials"
    assert session.get_calls[0]["headers"] == {"Authorization": "Bearer token"}
    assert session.get_calls[0]["params"]["maxPrice"] == "150.00"
    assert offers == [
        FlightOffer(
            airline="Lufthansa",
            origin="STR",
            destination="LIS",
            departure_time=datetime(2026, 7, 10, 6, 45),
            arrival_time=datetime(2026, 7, 10, 9, 5),
            duration="2h 20m",
            number_of_stops=1,
            price=Decimal("149.99"),
            currency="EUR",
            booking_url=None,
            source_provider="amadeus",
        )
    ]


def test_amadeus_provider_requires_credentials():
    provider = AmadeusProvider(client_id="", client_secret="")

    with pytest.raises(MissingCredentialsError):
        provider.search_flights(
            origin="STR",
            destination="LIS",
            departure_date=date(2026, 7, 10),
            return_date=None,
            max_price=None,
            currency="EUR",
        )


def test_amadeus_provider_handles_authentication_errors():
    provider = AmadeusProvider(
        client_id="bad",
        client_secret="bad",
        session=FakeSession(
            token_response=FakeResponse(401, {"error": "invalid_client"}),
            search_response=FakeResponse(200, {"data": []}),
        ),
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


def test_amadeus_provider_handles_rate_limits():
    provider = AmadeusProvider(
        client_id="client-id",
        client_secret="client-secret",
        session=FakeSession(
            token_response=FakeResponse(200, {"access_token": "token"}),
            search_response=FakeResponse(429, {"errors": []}),
        ),
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
