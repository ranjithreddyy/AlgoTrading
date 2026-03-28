"""Logging setup with JSON-formatted output."""

import json
import logging
import sys
from datetime import datetime, timezone


class _JsonFormatter(logging.Formatter):
    """Formats log records as single-line JSON."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "component": record.name,
            "level": record.levelname,
            "msg": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0] is not None:
            entry["exc"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


_CONFIGURED: set[str] = set()


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Return a logger with JSON-formatted console output.

    Safe to call multiple times with the same name; handlers are added only once.
    """
    logger = logging.getLogger(name)

    if name not in _CONFIGURED:
        logger.setLevel(level)
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(_JsonFormatter())
        logger.addHandler(handler)
        logger.propagate = False
        _CONFIGURED.add(name)

    return logger
