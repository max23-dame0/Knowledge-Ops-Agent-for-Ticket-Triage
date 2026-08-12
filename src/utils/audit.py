"""Append-only audit trail for agent decisions.

Writes one JSON line per agent run to data/audit/YYYY-MM-DD.jsonl so AI
decisions (especially escalation suggestions) are traceable after the fact.
The directory is git-ignored; retention is an operational concern.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_AUDIT_DIR = "data/audit"


class AuditTrail:
    """Thread-safe JSONL writer with per-day file rotation."""

    def __init__(self, directory: str = DEFAULT_AUDIT_DIR) -> None:
        self._directory = Path(directory)
        self._lock = threading.RLock()
        self._current_file: Path | None = None
        self._handle = None

    def _open_for_today(self) -> None:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        target = self._directory / f"{today}.jsonl"
        if self._current_file == target and self._handle is not None:
            return
        if self._handle is not None:
            self._handle.close()
        self._directory.mkdir(parents=True, exist_ok=True)
        self._handle = target.open("a", encoding="utf-8")
        self._current_file = target

    def record(self, event: dict[str, Any]) -> None:
        """Append one audit event (with timestamp) to today's JSONL file."""
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            **event,
        }
        with self._lock:
            self._open_for_today()
            self._handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
            self._handle.flush()


# Module-level singleton used by the agent runtime.
_default_trail = AuditTrail()


def get_audit_trail() -> AuditTrail:
    """Return the shared audit trail instance."""
    return _default_trail
