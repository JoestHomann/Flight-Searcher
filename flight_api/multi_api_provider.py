"""Aggregate multiple structured flight APIs behind one provider."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from storage import FlightOffer

from .base_provider import (
    FlightProvider,
    FlightProviderError,
    MissingCredentialsError,
    ProviderResponseError,
)


class MultiApiFlightProvider(FlightProvider):
    """Query configured structured APIs and merge their offers."""

    source_provider = "multi_api"

    def __init__(
        self,
        providers: list[FlightProvider],
        fail_fast: bool = False,
    ) -> None:
        self.providers = providers
        self.fail_fast = fail_fast

    def search_flights(
        self,
        origin: str,
        destination: str,
        departure_date: date,
        return_date: date | None,
        max_price: Decimal | None,
        currency: str,
    ) -> list[FlightOffer]:
        if not self.providers:
            raise MissingCredentialsError(
                "No structured API providers are configured. Add Amadeus or "
                "SerpApi credentials, or choose a browser-assisted provider."
            )

        offers: list[FlightOffer] = []
        errors = []
        for provider in self.providers:
            try:
                offers.extend(
                    provider.search_flights(
                        origin=origin,
                        destination=destination,
                        departure_date=departure_date,
                        return_date=return_date,
                        max_price=max_price,
                        currency=currency,
                    )
                )
            except MissingCredentialsError as exc:
                errors.append(str(exc))
            except FlightProviderError as exc:
                if self.fail_fast:
                    raise
                errors.append(str(exc))

        deduped_offers = self._dedupe_offers(offers)
        if deduped_offers:
            return deduped_offers
        if errors:
            raise ProviderResponseError(
                "No structured API provider returned flights. "
                + " | ".join(dict.fromkeys(errors))
            )
        return []

    @staticmethod
    def _dedupe_offers(offers: list[FlightOffer]) -> list[FlightOffer]:
        seen = set()
        deduped = []
        for offer in offers:
            key = (
                offer.airline,
                offer.origin,
                offer.destination,
                offer.departure_time,
                offer.arrival_time,
                offer.price,
                offer.currency,
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(offer)
        return deduped
