"""Application entry point for the flight search GUI."""

from gui.app import run_app
from logging_config import configure_logging


def main() -> None:
    configure_logging()
    run_app()


if __name__ == "__main__":
    main()
