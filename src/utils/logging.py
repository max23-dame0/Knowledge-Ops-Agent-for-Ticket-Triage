"""Structured logging helpers with request_id correlation support.

Provides:
- JSON-formatted logs (LOG_FORMAT=json, recommended for deployed environments)
  or human-friendly text (LOG_FORMAT=text, default for local development)
- request_id correlation via contextvars so a single request can be traced
  across agent run / tool calls / eval samples
"""

from __future__ import annotations

import json
import logging
import os
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


def set_request_id(request_id: str | None) -> None:
    """Set the request_id for the current context (thread-local)."""
    if request_id is None:
        request_id_var.set(None)
    else:
        request_id_var.set(str(request_id))


def get_request_id() -> str | None:
    """Return the request_id bound to the current context, if any."""
    return request_id_var.get()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class JsonFormatter(logging.Formatter):
    """Format log records as single-line JSON for machine parsing."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": _now_iso(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = get_request_id()
        if request_id:
            payload["request_id"] = request_id
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def get_logger(name: str = "knowledge_ops") -> logging.Logger:
    """Return a logger with the configured format.

    Format is controlled by the LOG_FORMAT environment variable:
    - "json": structured single-line JSON (recommended for deployed envs)
    - "text": human-friendly local development format (default)
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    fmt = os.getenv("LOG_FORMAT", "text").strip().lower()
    handler = logging.StreamHandler()
    if fmt == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("[%(levelname)s] %(name)s: %(message)s"))
    logger.addHandler(handler)

    level = os.getenv("LOG_LEVEL", "INFO").strip().upper()
    logger.setLevel(getattr(logging, level, logging.INFO))
    logger.propagate = False
    return logger
