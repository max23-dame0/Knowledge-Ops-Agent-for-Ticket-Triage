"""Minimal logging helpers for local development."""

from __future__ import annotations

import logging


def get_logger(name: str = "knowledge_ops") -> logging.Logger:
    """Return a console logger with a small local-development format."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(levelname)s] %(name)s: %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger
