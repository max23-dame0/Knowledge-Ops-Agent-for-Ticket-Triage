"""A3: experience pool with jsonl persistence, capacity, dedupe, and search."""

from __future__ import annotations

import threading
from pathlib import Path

from src.improvement.schemas import ExperienceEntry
from src.rag.hybrid import tokenize
from src.utils.logging import get_logger

logger = get_logger(__name__)

DEFAULT_EXPERIENCE_DIR = "data/experience"
DEFAULT_MAX_ENTRIES = 100


def _signature(entry: ExperienceEntry) -> tuple[str, str, str]:
    """Dedupe key for an entry (situation + action + lesson)."""
    return (entry.situation, entry.action, entry.lesson)


def _keyword_overlap(query_tokens: set[str], entry: ExperienceEntry) -> float:
    """Score an entry by token overlap against the query (0 = no match)."""
    entry_tokens = set(
        tokenize(entry.situation) + tokenize(entry.action) + tokenize(entry.lesson)
    )
    if not query_tokens:
        return 0.0
    return len(query_tokens & entry_tokens) / len(query_tokens)


class ExperienceStore:
    """Thread-safe jsonl experience pool with capacity eviction and dedupe."""

    def __init__(self, path: str = DEFAULT_EXPERIENCE_DIR, max_entries: int = DEFAULT_MAX_ENTRIES) -> None:
        self._path = Path(path)
        if self._path.suffix == "":
            self._path = self._path / "experiences.jsonl"
        self._max_entries = max_entries
        self._lock = threading.RLock()

    def load(self) -> list[ExperienceEntry]:
        """Read all entries from disk in insertion order."""
        with self._lock:
            if not self._path.exists():
                return []
            entries: list[ExperienceEntry] = []
            for line in self._path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(ExperienceEntry.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001 - skip corrupt lines, keep the rest
                    logger.warning("experience_store_corrupt_line | path=%s | error=%s", self._path.name, exc)
            return entries

    def add(self, entry: ExperienceEntry) -> bool:
        """Append an entry; return False when it duplicates an existing one."""
        with self._lock:
            entries = self._load_unsafe()
            signature = _signature(entry)
            if any(_signature(existing) == signature for existing in entries):
                logger.info("experience_store_dedupe | situation=%s", entry.situation[:40])
                return False

            entries.append(entry)
            if len(entries) > self._max_entries:
                removed = entries[: len(entries) - self._max_entries]
                entries = entries[-self._max_entries :]
                logger.info(
                    "experience_store_evict | removed=%d | kept=%d",
                    len(removed),
                    len(entries),
                )
            self._persist_unsafe(entries)
            logger.info("experience_store_add | situation=%s | total=%d", entry.situation[:40], len(entries))
            return True

    def downgrade(self, entry: ExperienceEntry) -> bool:
        """Flip an existing entry's source to `rejected` in place.

        Returns True when a matching entry was found and downgraded. The
        dedupe signature ignores `source`, so a rejected copy cannot be
        appended separately; in-place downgrade avoids that trap.
        """
        with self._lock:
            entries = self._load_unsafe()
            signature = _signature(entry)
            changed = False
            for index, existing in enumerate(entries):
                if _signature(existing) == signature and existing.source != "rejected":
                    entries[index] = existing.model_copy(update={"source": "rejected"})
                    changed = True
            if changed:
                self._persist_unsafe(entries)
            return changed

    def search(self, query: str, top_k: int = 3) -> list[ExperienceEntry]:
        """Return entries ranked by keyword overlap with the query."""
        query_tokens = set(tokenize(query))
        if not query_tokens:
            return []
        entries = self.load()
        scored = [
            (entry, _keyword_overlap(query_tokens, entry))
            for entry in entries
        ]
        scored = [(entry, score) for entry, score in scored if score > 0]
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return [entry for entry, _ in scored[:top_k]]

    def _load_unsafe(self) -> list[ExperienceEntry]:
        """Load without acquiring the lock (callers hold it)."""
        if not self._path.exists():
            return []
        entries: list[ExperienceEntry] = []
        for line in self._path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(ExperienceEntry.model_validate_json(line))
            except Exception as exc:  # noqa: BLE001 - skip corrupt lines
                logger.warning("experience_store_corrupt_line | path=%s | error=%s", self._path.name, exc)
        return entries

    def _persist_unsafe(self, entries: list[ExperienceEntry]) -> None:
        """Write all entries to disk (callers hold the lock)."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        lines = [entry.model_dump_json() for entry in entries]
        self._path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
