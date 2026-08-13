"""A1: extract structured failure samples from offline eval result CSVs."""

from __future__ import annotations

import csv
from pathlib import Path

from pydantic import BaseModel

from src.utils.logging import get_logger

logger = get_logger(__name__)

#: Boolean column keys that signal a specific behaviour check failed.
_ERROR_TYPE_COLUMNS: tuple[tuple[str, str], ...] = (
    ("route_ok", "route_error"),
    ("tool_ok", "tool_error"),
    ("clarify_ok", "clarification_error"),
    ("grounding_ok", "grounding_error"),
    ("refusal_ok", "refusal_error"),
)


class FailureSample(BaseModel):
    """Structured failure trajectory for one eval sample."""

    sample_id: str
    question: str
    expected_route: str
    predicted_route: str
    error_types: list[str]
    evidence_expected: bool
    evidence_present: bool
    execution_error: str = ""


def _to_bool(value: str | None) -> bool:
    """Convert CSV boolean-like strings into Python booleans."""
    return (value or "").strip().lower() == "true"


def _classify_error_types(row: dict[str, str]) -> list[str]:
    """Derive error type labels from the boolean check columns."""
    if row.get("error", "").strip():
        return ["execution_error"]
    return [
        error_type
        for column, error_type in _ERROR_TYPE_COLUMNS
        if not _to_bool(row.get(column))
    ]


def extract_failure_samples(csv_path: str | Path) -> list[FailureSample]:
    """Load an offline eval result CSV and return only failing samples."""
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"eval result CSV not found: {path}")

    samples: list[FailureSample] = []
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            summary = (row.get("pass_fail_summary") or "").strip().lower()
            has_error = bool((row.get("error") or "").strip())
            if summary == "pass" and not has_error:
                continue
            samples.append(
                FailureSample(
                    sample_id=row.get("id", ""),
                    question=row.get("question", ""),
                    expected_route=row.get("expected_route", ""),
                    predicted_route=row.get("predicted_route", ""),
                    error_types=_classify_error_types(row),
                    evidence_expected=_to_bool(row.get("evidence_expected")),
                    evidence_present=_to_bool(row.get("evidence_present")),
                    execution_error=(row.get("error") or "").strip(),
                )
            )

    logger.info("failure_extraction | samples=%d path=%s", len(samples), path.name)
    return samples
