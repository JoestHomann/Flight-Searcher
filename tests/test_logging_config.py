import logging

from logging_config import configure_logging


def test_configure_logging_creates_log_directory(tmp_path):
    log_path = tmp_path / "logs" / "flight_search.log"

    configure_logging(log_path)
    logging.getLogger("test").info("hello")

    assert log_path.parent.exists()
