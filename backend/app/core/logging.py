"""Logging configuration with structured JSON output and request correlation."""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from typing import Any

LOG_FORMAT_TEXT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Correlation context populated by middleware / auth dependencies. Reading these
# never raises — empty strings mean "not yet set on this task".
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")
org_id_ctx: ContextVar[str] = ContextVar("org_id", default="")
user_id_ctx: ContextVar[str] = ContextVar("user_id", default="")


_RESERVED_LOG_RECORD_ATTRS = {
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "message", "asctime", "taskName",
}


class JsonFormatter(logging.Formatter):
    """Single-line JSON formatter that injects correlation context."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }

        request_id = request_id_ctx.get()
        org_id = org_id_ctx.get()
        user_id = user_id_ctx.get()
        if request_id:
            payload["request_id"] = request_id
        if org_id:
            payload["org_id"] = org_id
        if user_id:
            payload["user_id"] = user_id

        for key, value in record.__dict__.items():
            if key in _RESERVED_LOG_RECORD_ATTRS or key.startswith("_"):
                continue
            payload[key] = value

        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


def setup_logging(log_level: str = "DEBUG", json_output: bool = True) -> None:
    """Configure logging for the application.

    json_output=True emits one JSON object per line (production / staging).
    json_output=False keeps the legacy human-readable format (local dev).
    """
    level = getattr(logging, log_level.upper(), logging.DEBUG)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    if json_output:
        console_handler.setFormatter(JsonFormatter())
    else:
        console_handler.setFormatter(logging.Formatter(LOG_FORMAT_TEXT))
    root_logger.addHandler(console_handler)

    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("asyncpg").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance."""
    return logging.getLogger(name)


def bind_request_context(
    *,
    request_id: str | None = None,
    org_id: str | None = None,
    user_id: str | None = None,
) -> None:
    """Attach correlation IDs to the current async task's logging context."""
    if request_id is not None:
        request_id_ctx.set(request_id)
    if org_id is not None:
        org_id_ctx.set(org_id)
    if user_id is not None:
        user_id_ctx.set(user_id)
