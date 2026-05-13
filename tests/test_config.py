from pathlib import Path

from config import load_config, save_env_setting


def test_load_config_reads_environment(monkeypatch):
    monkeypatch.setenv("FLIGHT_API_PROVIDER", "amadeus")
    monkeypatch.setenv("AMADEUS_CLIENT_ID", "client-id")
    monkeypatch.setenv("AMADEUS_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("DEFAULT_CURRENCY", "usd")
    monkeypatch.setenv("DEFAULT_ORIGIN", "str")
    monkeypatch.setenv("DATABASE_PATH", "data/flights.db")
    monkeypatch.setenv("AMADEUS_BASE_URL", "https://example.test/")
    monkeypatch.setenv("SERPAPI_API_KEY", "serp-key")
    monkeypatch.setenv("SERPAPI_BASE_URL", "https://serpapi.test/search")
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
    assert config.serpapi_api_key == "serp-key"
    assert config.serpapi_credentials_configured is True
    assert config.serpapi_base_url == "https://serpapi.test/search"
    assert config.request_timeout_seconds == 7.5


def test_save_env_setting_updates_or_creates_key(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("DEFAULT_CURRENCY=EUR\nFLIGHT_API_PROVIDER=mock\n", encoding="utf-8")

    save_env_setting("FLIGHT_API_PROVIDER", "serpapi_google_flights", env_path)
    save_env_setting("SERPAPI_API_KEY", "serp-key", env_path)

    assert env_path.read_text(encoding="utf-8").splitlines() == [
        "DEFAULT_CURRENCY=EUR",
        "FLIGHT_API_PROVIDER=serpapi_google_flights",
        "SERPAPI_API_KEY=serp-key",
    ]
