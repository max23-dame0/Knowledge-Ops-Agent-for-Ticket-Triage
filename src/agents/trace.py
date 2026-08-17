"""Decision trace: structured, serializable record of one agent run.

The trace is the backbone of the replay corpus: every deterministic decision
and LLM interaction is captured, so evaluation can assert behavior offline
and PRs can diff decision changes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

TRACE_DIR_DEFAULT = "data/replay/sessions"


class DecisionTrace(BaseModel):
    """One complete decision trace for an agent run."""

    run_id: str = Field(description="Unique run id (request id by default).")
    question: str = Field(description="The user question.")
    stage: str = Field(default="decision", description="Trace stage marker.")
    guardrail: dict[str, Any] = Field(default_factory=dict)
    route_fn: dict[str, Any] = Field(default_factory=dict)
    clarify: dict[str, Any] = Field(default_factory=dict)
    plan: dict[str, Any] = Field(default_factory=dict)
    llm: dict[str, Any] = Field(default_factory=dict)
    final: dict[str, Any] = Field(default_factory=dict)

    def to_record(self) -> dict[str, Any]:
        """Return the JSON-serializable trace record."""
        return self.model_dump()


class TraceRecorder:
    """Append traces as JSONL records for replay and evaluation."""

    def __init__(self, directory: str = TRACE_DIR_DEFAULT) -> None:
        self._directory = Path(directory)

    @property
    def directory(self) -> Path:
        return self._directory

    def write(self, trace: DecisionTrace) -> Path:
        """Append a trace line to the per-run JSONL file."""
        self._directory.mkdir(parents=True, exist_ok=True)
        path = self._directory / f"{trace.run_id}.jsonl"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(trace.to_record(), ensure_ascii=False) + "\n")
        return path
