"""Observability: structured logging (text/JSON), request IDs, and metrics.

Keeps zero external dependencies — metrics are emitted as structured log records
so any log aggregator can pick them up without a stats backend.
"""

from __future__ import annotations

import json
import logging
import secrets

LOGGER_NAME = "antigravity_bridge"
_logger = logging.getLogger(LOGGER_NAME)

# Extra attributes copied onto structured (JSON) log output.
_STRUCTURED_FIELDS = (
    "event",
    "request_id",
    "duration_ms",
    "success",
    "timed_out",
    "model",
    "attempt",
    "tool",
)


class JsonFormatter(logging.Formatter):
    """Emit each log record as a single-line JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in _STRUCTURED_FIELDS:
            if field in record.__dict__:
                payload[field] = record.__dict__[field]
        if record.exc_info:
            payload["error"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


_TEXT_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


def setup_logging(level: str = "INFO", fmt: str = "text") -> None:
    """Configure root logging with a text or JSON handler."""
    numeric_level = getattr(logging, str(level).upper(), logging.INFO)
    formatter: logging.Formatter
    if str(fmt).lower() == "json":
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(_TEXT_FORMAT)

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    root = logging.getLogger()
    # Replace existing handlers without mutating the list object in place, so a
    # host application that inspects `root.handlers` is not surprised. Net effect
    # is still a single handler (idempotent on repeated calls).
    while root.handlers:
        root.removeHandler(root.handlers[0])
    root.addHandler(handler)
    root.setLevel(numeric_level)
    _logger.setLevel(numeric_level)


def new_request_id() -> str:
    """Return a short, unique request identifier."""
    return secrets.token_hex(8)


def record_call(**fields: object) -> None:
    """Emit a structured ``agy.call`` metric record."""
    _logger.info("agy.call", extra={"event": "agy.call", **fields})


def get_logger() -> logging.Logger:
    """Return the package logger."""
    return _logger
