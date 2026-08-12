"""Ticket data repository: in-memory indexed access to the local ticket dataset.

Loads the JSON dataset once and indexes it by normalized ticket id, giving
O(1) lookups instead of a full scan per request. The dataset is treated as
read-only (append-only by convention); refresh() reloads from disk when the
file changes.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from src.utils.ticket_id import normalize_ticket_id

DEFAULT_TICKETS_PATH = "data/tickets.json"


class TicketRepository:
    """Thread-safe in-memory repository over the local tickets JSON file."""

    def __init__(self, path: str = DEFAULT_TICKETS_PATH) -> None:
        self._path = Path(path)
        self._lock = threading.RLock()
        self._by_id: dict[str, dict[str, Any]] = {}
        self._loaded = False
        self.refresh()

    @property
    def path(self) -> Path:
        return self._path

    def refresh(self) -> None:
        """Reload the dataset from disk and rebuild the id index."""
        with self._lock:
            if not self._path.exists():
                self._by_id = {}
                self._loaded = False
                return
            records = json.loads(self._path.read_text(encoding="utf-8-sig"))
            by_id: dict[str, dict[str, Any]] = {}
            for item in records:
                stored_id = normalize_ticket_id(str(item.get("ticket_id", "")), allow_bare_numeric=True)
                if stored_id:
                    by_id[stored_id] = item
            self._by_id = by_id
            self._loaded = True

    @property
    def loaded(self) -> bool:
        return self._loaded

    def count(self) -> int:
        """Return the number of indexed ticket records."""
        with self._lock:
            return len(self._by_id)

    def find_by_id(self, ticket_id: str) -> dict[str, Any] | None:
        """Return the raw ticket record for a normalized id, or None."""
        normalized = normalize_ticket_id(ticket_id, allow_bare_numeric=True)
        if normalized is None:
            return None
        with self._lock:
            return self._by_id.get(normalized)


# Module-level singleton so all callers share one in-memory dataset.
_default_repository = TicketRepository()


def get_ticket_repository() -> TicketRepository:
    """Return the shared ticket repository instance."""
    return _default_repository
