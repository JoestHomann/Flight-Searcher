"""Application logging setup."""

from __future__ import annotations

import logging
from pathlib import Path


def configure_logging(log_path: str | Path = "storage/flight_search.log") -> None:
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=path,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
