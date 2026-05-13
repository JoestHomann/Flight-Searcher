from pathlib import Path

from config import load_config


def test_load_config_reads_environment(monkeypatch):
    monkeypatch.setenv("FLIGHT_API_PROVIDER", "amadeus")
    monkeypatch.setenv("AMADEUS_CLIENT_ID", "client-id")
    monkeypatch.setenv("AMADEUS_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("DEFAULT_CURRENCY", "usd")
    monkeypatch.setenv("DEFAULT_ORIGIN", "str")
    monkeypatch.setenv("DATABASE_PATH", "data/flights.db")
    monkeypatch.setenv("AMADEUS_BASE_URL", "https://example.test/")
    monkeypatch.setenv("REQUEST_TIMEOUT_SECONDS", "7.5")

    config = load_config(env_path=Path("missing.env"))

    assert config.flight_api_provider == "amadeus"
    assert config.amadeus_client_id == "client-id"
    assert config.amadeus_client_secret == "client-secret"
    assert config.amadeus_credentials_configured is True
    assert config.default_currency == "USD"
    assert config.default_origin == "STR"
    assert config.database_path.name == "flights.db"
    assert config.amadeus_base_url == "https://example.test"
    assert config.request_timeout_seconds == 7.5
