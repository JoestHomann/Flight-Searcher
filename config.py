"""Configuration helpers for the flight search application."""

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = (
    Path(sys.executable).resolve().parent
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parent
)


@dataclass(frozen=True, slots=True)
class AppConfig:
    flight_api_provider: str
    amadeus_client_id: str
    amadeus_client_secret: str
    default_currency: str
    default_origin: str
    database_path: Path
    amadeus_base_url: str
    request_timeout_seconds: float
    serpapi_api_key: str = ""
    serpapi_base_url: str = "https://serpapi.com/search"

    @property
    def amadeus_credentials_configured(self) -> bool:
        return bool(self.amadeus_client_id and self.amadeus_client_secret)

    @property
    def serpapi_credentials_configured(self) -> bool:
        return bool(self.serpapi_api_key)


def load_config(env_path: str | Path | None = None) -> AppConfig:
    """Load application settings from environment variables and .env."""
    load_dotenv(Path(env_path) if env_path else BASE_DIR / ".env")
    return AppConfig(
        flight_api_provider=os.getenv("FLIGHT_API_PROVIDER", "mock").strip().lower(),
        amadeus_client_id=os.getenv("AMADEUS_CLIENT_ID", "").strip(),
        amadeus_client_secret=os.getenv("AMADEUS_CLIENT_SECRET", "").strip(),
        default_currency=os.getenv("DEFAULT_CURRENCY", "EUR").strip().upper(),
        default_origin=os.getenv("DEFAULT_ORIGIN", "").strip().upper(),
        database_path=_resolve_database_path(
            os.getenv("DATABASE_PATH", "storage/flight_search.db")
        ),
        amadeus_base_url=os.getenv(
            "AMADEUS_BASE_URL", "https://test.api.amadeus.com"
        ).strip().rstrip("/"),
        request_timeout_seconds=float(os.getenv("REQUEST_TIMEOUT_SECONDS", "20")),
        serpapi_api_key=os.getenv("SERPAPI_API_KEY", "").strip(),
        serpapi_base_url=os.getenv(
            "SERPAPI_BASE_URL", "https://serpapi.com/search"
        ).strip(),
    )


def save_env_setting(
    key: str,
    value: str,
    env_path: str | Path | None = None,
) -> Path:
    """Create or update one simple KEY=value setting in a local .env file."""
    path = Path(env_path) if env_path else BASE_DIR / ".env"
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    setting = f"{key}={value}"
    updated = False
    new_lines = []
    for line in lines:
        if line.startswith(f"{key}="):
            new_lines.append(setting)
            updated = True
        else:
            new_lines.append(line)
    if not updated:
        new_lines.append(setting)
    path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    return path


def _resolve_database_path(value: str) -> Path:
    database_path = Path(value.strip() or "storage/flight_search.db")
    if database_path.is_absolute():
        return database_path
    return BASE_DIR / database_path
