"""Replay store: persistence for golden decision traces and live sessions.

The replay corpus is the bridge between evaluation and the project itself:
- sessions/<run_id>.jsonl  hold every decision trace an agent run produced
- golden/samples.jsonl     hold the curated traces that evaluation replays

Golden traces let offline tests assert behavior without a live LLM and let
PRs diff decision changes per sample.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPLAY_DIR_DEFAULT = "data/replay"
GOLDEN_SAMPLES_DEFAULT = "golden/samples.jsonl"


class ReplayStore:
    """Read/write access to replay session files and the golden corpus."""

    def __init__(self, directory: str = REPLAY_DIR_DEFAULT) -> None:
        self._directory = Path(directory)

    @property
    def directory(self) -> Path:
        return self._directory

    def session_path(self, run_id: str) -> Path:
        """Return the session file path for a run id."""
        return self._directory / "sessions" / f"{run_id}.jsonl"

    def golden_path(self, path: str = GOLDEN_SAMPLES_DEFAULT) -> Path:
        """Return the golden corpus file path."""
        return self._directory / path

    def load_golden(self, path: str = GOLDEN_SAMPLES_DEFAULT) -> list[dict[str, Any]]:
        """Load all golden trace records (missing corpus yields an empty list)."""
        golden = self.golden_path(path)
        if not golden.exists():
            return []
        return [json.loads(line) for line in golden.read_text(encoding="utf-8").splitlines() if line.strip()]

    def append_golden(self, records: list[dict[str, Any]], path: str = GOLDEN_SAMPLES_DEFAULT) -> Path:
        """Append trace records to the golden corpus."""
        golden = self.golden_path(path)
        golden.parent.mkdir(parents=True, exist_ok=True)
        with golden.open("a", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        return golden

    def load_session(self, run_id: str) -> list[dict[str, Any]]:
        """Load the records of one session (missing file yields an empty list)."""
        session = self.session_path(run_id)
        if not session.exists():
            return []
        return [json.loads(line) for line in session.read_text(encoding="utf-8").splitlines() if line.strip()]

    def iter_sessions(self) -> list[dict[str, Any]]:
        """Load all session records across run ids."""
        sessions_dir = self._directory / "sessions"
        if not sessions_dir.exists():
            return []
        records: list[dict[str, Any]] = []
        for session in sorted(sessions_dir.glob("*.jsonl")):
            records.extend(self.load_session(session.stem))
        return records
