"""Configuration helpers for the flight search application."""

from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent


def load_config() -> None:
    """Load local environment variables when a .env file exists."""
    load_dotenv(BASE_DIR / ".env")
