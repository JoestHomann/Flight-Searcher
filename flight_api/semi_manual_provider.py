"""Semi-manual site provider and clipboard import parser."""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation

from storage import FlightOffer

from .browser_assisted_provider import (
    SEMI_MANUAL_SITE_PROVIDER_PREFIX,
    BrowserAssistedFlightProvider,
)
from .site_sources import DEFAULT_FLIGHT_SEARCH_SITES, FlightSearchSite


SEMI_MANUAL_CLIPBOARD_PROVIDER_PREFIX = "semi_manual_clipboard:"
PRICE_PATTERN = re.compile(
    r"(?:(?P<prefix_code>EUR|USD|GBP)\s*)?"
    r"(?P<prefix_symbol>[€$£])?\s*"
    r"(?P<amount>\d{1,4}(?:[.,]\d{3})*(?:[.,]\d{2})?|\d{1,6})"
    r"\s*(?P<suffix_code>EUR|USD|GBP)?"
    r"\s*(?P<suffix_symbol>[€$£])?",
    re.IGNORECASE,
)
TIME_RANGE_PATTERN = re.compile(
    r"(?P<start>\d{1,2}:\d{2}\s*(?:AM|PM)?)"
    r"\s*(?:-|–|—|to)\s*"
    r"(?P<end>\d{1,2}:\d{2}\s*(?:AM|PM)?)",
    re.IGNORECASE,
)
DURATION_PATTERN = re.compile(
    r"\b(?:(?P<hours>\d+)\s*(?:h|hr|hrs|hour|hours))?"
    r"\s*(?:(?P<minutes>\d+)\s*(?:m|min|mins|minute|minutes))?\b",
    re.IGNORECASE,
)
STOP_PATTERN = re.compile(r"\b(?P<count>\d+)\s+stops?\b", re.IGNORECASE)
CURRENCY_SYMBOLS = {"€": "EUR", "$": "USD", "£": "GBP"}


class SemiManualSiteFlightProvider(BrowserAssistedFlightProvider):
    """Open source sites, then let the GUI import copied result text."""

    source_provider = "semi_manual_site_check"
    handoff_provider_prefix = SEMI_MANUAL_SITE_PROVIDER_PREFIX

    def __init__(
        self,
        sites: tuple[FlightSearchSite, ...] = DEFAULT_FLIGHT_SEARCH_SITES,
        open_pages: bool = True,
    ) -> None:
        super().__init__(sites=sites, open_pages=open_pages)


def parse_clipboard_flight_offers(
    clipboard_text: str,
    source_offer: FlightOffer,
) -> list[FlightOffer]:
    """Convert copied flight-result text into normalized flight offers."""
    lines = _clean_lines(clipboard_text)
    if not lines:
        return []

    offers = []
    for line_index, line in enumerate(lines):
        for price_match in PRICE_PATTERN.finditer(line):
            currency = _currency_from_match(price_match, source_offer.currency)
            if not _has_currency_marker(price_match):
                continue
            try:
                price = _parse_price(price_match.group("amount"))
            except InvalidOperation:
                continue

            context = _context_lines(lines, line_index)
            departure_time, arrival_time = _times_from_context(
                context,
                source_offer.departure_time.date(),
            )
            offers.append(
                FlightOffer(
                    airline=_airline_from_context(context),
                    origin=source_offer.origin,
                    destination=source_offer.destination,
                    departure_time=departure_time,
                    arrival_time=arrival_time,
                    duration=_duration_from_context(
                        context,
                        departure_time,
                        arrival_time,
                    ),
                    number_of_stops=_stops_from_context(context),
                    price=price,
                    currency=currency,
                    booking_url=source_offer.booking_url,
                    source_provider=_clipboard_provider_name(source_offer),
                )
            )
    return _dedupe_offers(offers)


def is_semi_manual_source_offer(offer: FlightOffer) -> bool:
    return offer.source_provider.startswith(SEMI_MANUAL_SITE_PROVIDER_PREFIX)


def _clean_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _context_lines(lines: list[str], line_index: int, radius: int = 4) -> list[str]:
    start = max(line_index - radius, 0)
    end = min(line_index + radius + 1, len(lines))
    return lines[start:end]


def _has_currency_marker(match: re.Match[str]) -> bool:
    return any(
        match.group(name)
        for name in (
            "prefix_code",
            "prefix_symbol",
            "suffix_code",
            "suffix_symbol",
        )
    )


def _currency_from_match(match: re.Match[str], fallback: str) -> str:
    code = match.group("prefix_code") or match.group("suffix_code")
    if code:
        return code.upper()
    symbol = match.group("prefix_symbol") or match.group("suffix_symbol")
    return CURRENCY_SYMBOLS.get(symbol, fallback.upper())


def _parse_price(value: str) -> Decimal:
    clean_value = value.strip()
    if "," in clean_value and "." in clean_value:
        if clean_value.rfind(",") > clean_value.rfind("."):
            clean_value = clean_value.replace(".", "").replace(",", ".")
        else:
            clean_value = clean_value.replace(",", "")
    elif "," in clean_value:
        clean_value = clean_value.replace(".", "").replace(",", ".")
    return Decimal(clean_value)


def _times_from_context(
    context: list[str],
    departure_date: date,
) -> tuple[datetime, datetime]:
    context_text = " ".join(context)
    match = TIME_RANGE_PATTERN.search(context_text)
    if not match:
        fallback = datetime.combine(departure_date, time())
        return fallback, fallback

    departure_time = _parse_time(match.group("start"))
    arrival_time = _parse_time(match.group("end"))
    departure_at = datetime.combine(departure_date, departure_time)
    arrival_at = datetime.combine(departure_date, arrival_time)
    if arrival_at < departure_at:
        arrival_at += timedelta(days=1)
    return departure_at, arrival_at


def _parse_time(value: str) -> time:
    clean_value = value.strip().upper().replace(" ", "")
    for fmt in ("%H:%M", "%I:%M%p"):
        try:
            return datetime.strptime(clean_value, fmt).time()
        except ValueError:
            continue
    raise ValueError(f"Unsupported time: {value}")


def _airline_from_context(context: list[str]) -> str:
    for line in context:
        if not re.search(r"[A-Za-z]", line):
            continue
        if PRICE_PATTERN.search(line) or TIME_RANGE_PATTERN.search(line):
            continue
        lower_line = line.lower()
        if any(token in lower_line for token in ("stop", "hour", "minute", "flight")):
            continue
        if len(line) <= 60:
            return line.replace("Operated by ", "").strip()
    return "Manual import"


def _duration_from_context(
    context: list[str],
    departure_time: datetime,
    arrival_time: datetime,
) -> str:
    for line in context:
        duration = _duration_from_line(line)
        if duration:
            return duration
    total_minutes = int((arrival_time - departure_time).total_seconds() // 60)
    return _format_duration_minutes(total_minutes) if total_minutes > 0 else ""


def _duration_from_line(line: str) -> str | None:
    for match in DURATION_PATTERN.finditer(line):
        hours = int(match.group("hours") or 0)
        minutes = int(match.group("minutes") or 0)
        if hours or minutes:
            return _format_duration_parts(hours, minutes)
    return None


def _format_duration_parts(hours: int, minutes: int) -> str:
    parts = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    return " ".join(parts)


def _format_duration_minutes(total_minutes: int) -> str:
    hours, minutes = divmod(total_minutes, 60)
    return _format_duration_parts(hours, minutes)


def _stops_from_context(context: list[str]) -> int:
    context_text = " ".join(context).lower()
    if "nonstop" in context_text or "non-stop" in context_text or "direct" in context_text:
        return 0
    match = STOP_PATTERN.search(context_text)
    return int(match.group("count")) if match else 0


def _clipboard_provider_name(source_offer: FlightOffer) -> str:
    source_key = source_offer.source_provider.split(":", 1)[-1]
    return f"{SEMI_MANUAL_CLIPBOARD_PROVIDER_PREFIX}{source_key}"


def _dedupe_offers(offers: list[FlightOffer]) -> list[FlightOffer]:
    seen = set()
    deduped = []
    for offer in offers:
        key = (
            offer.airline,
            offer.departure_time,
            offer.arrival_time,
            offer.price,
            offer.currency,
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(offer)
    return sorted(deduped, key=lambda offer: offer.price)
