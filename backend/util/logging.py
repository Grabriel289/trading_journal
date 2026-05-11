"""Structured logging setup. Imported (and called) once from main.py.

`LOG_FORMAT=json` emits one JSON object per line — friendly for log shippers.
`LOG_FORMAT=text` (default) emits the classic single-line dev format.
"""
import logging
import sys

from backend.config import LOG_FORMAT, LOG_LEVEL


_TEXT_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"


def setup_logging() -> None:
    root = logging.getLogger()
    root.setLevel(LOG_LEVEL)

    # Clear any handlers Uvicorn / others may have already added so we don't double-log.
    for h in list(root.handlers):
        root.removeHandler(h)

    handler = logging.StreamHandler(sys.stdout)

    if LOG_FORMAT == "json":
        try:
            from pythonjsonlogger import jsonlogger
            formatter = jsonlogger.JsonFormatter(
                "%(asctime)s %(name)s %(levelname)s %(message)s",
                rename_fields={"asctime": "timestamp", "levelname": "level"},
                timestamp=True,
            )
        except ImportError:
            # Fall back to text if python-json-logger isn't installed
            formatter = logging.Formatter(_TEXT_FORMAT)
    else:
        formatter = logging.Formatter(_TEXT_FORMAT)

    handler.setFormatter(formatter)
    root.addHandler(handler)

    # Quiet down noisy libs
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("apscheduler.scheduler").setLevel(logging.WARNING)
    logging.getLogger("apscheduler.executors.default").setLevel(logging.WARNING)
