"""Application logging setup."""

from __future__ import annotations

import logging
from pathlib import Path

from config import BASE_DIR


def configure_logging(log_path: str | Path | None = None) -> None:
    path = Path(log_path) if log_path is not None else BASE_DIR / "storage/flight_search.log"
    if not path.is_absolute():
        path = BASE_DIR / path
    path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=path,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
