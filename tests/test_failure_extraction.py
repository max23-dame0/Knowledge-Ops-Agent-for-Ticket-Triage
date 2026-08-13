"""Tests for A1 failure trajectory extraction from offline eval result CSVs."""

from __future__ import annotations

import csv
from pathlib import Path

from src.evals.failure_extraction import FailureSample, extract_failure_samples

CSV_FIELDS = [
    "id",
    "question",
    "expected_route",
    "predicted_route",
    "should_clarify",
    "predicted_clarify",
    "expected_tool",
    "predicted_tool",
    "unsafe",
    "refused",
    "evidence_expected",
    "evidence_present",
    "route_ok",
    "tool_ok",
    "clarify_ok",
    "grounding_ok",
    "refusal_ok",
    "pass_fail_summary",
    "error",
]


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    """Write a synthetic offline eval result CSV for tests."""
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _base_row(**overrides: str) -> dict[str, str]:
    """Return a fully passing sample row, overridden per test."""
    row: dict[str, str] = {
        "id": "E001",
        "question": "VPN 登录失败提示 token 过期怎么办",
        "expected_route": "kb",
        "predicted_route": "kb",
        "should_clarify": "False",
        "predicted_clarify": "False",
        "expected_tool": "search_kb",
        "predicted_tool": "search_kb",
        "unsafe": "False",
        "refused": "False",
        "evidence_expected": "True",
        "evidence_present": "True",
        "route_ok": "True",
        "tool_ok": "True",
        "clarify_ok": "True",
        "grounding_ok": "True",
        "refusal_ok": "True",
        "pass_fail_summary": "pass",
        "error": "",
    }
    row.update(overrides)
    return row


def test_extract_returns_no_samples_when_all_pass(tmp_path: Path) -> None:
    """All-passing CSV yields an empty failure sample list."""
    csv_path = tmp_path / "results.csv"
    _write_csv(csv_path, [_base_row()])

    samples = extract_failure_samples(csv_path)

    assert samples == []


def test_extract_collects_route_error_with_full_fields(tmp_path: Path) -> None:
    """A route failure row becomes a FailureSample with complete fields."""
    csv_path = tmp_path / "results.csv"
    _write_csv(
        csv_path,
        [
            _base_row(
                id="E002",
                question="多个用户反馈服务中断",
                predicted_route="clarify",
                route_ok="False",
                pass_fail_summary="fail",
            ),
        ],
    )

    samples = extract_failure_samples(csv_path)

    assert len(samples) == 1
    sample = samples[0]
    assert isinstance(sample, FailureSample)
    assert sample.sample_id == "E002"
    assert sample.question == "多个用户反馈服务中断"
    assert sample.expected_route == "kb"
    assert sample.predicted_route == "clarify"
    assert sample.error_types == ["route_error"]
    assert sample.evidence_expected is True
    assert sample.evidence_present is True
    assert sample.execution_error == ""


def test_extract_classifies_multiple_error_types(tmp_path: Path) -> None:
    """A row failing route+tool+grounding carries all three error types."""
    csv_path = tmp_path / "results.csv"
    _write_csv(
        csv_path,
        [
            _base_row(
                id="E003",
                predicted_route="ticket",
                predicted_tool="get_ticket_status",
                route_ok="False",
                tool_ok="False",
                grounding_ok="False",
                pass_fail_summary="fail",
            ),
        ],
    )

    samples = extract_failure_samples(csv_path)

    assert samples[0].error_types == ["route_error", "tool_error", "grounding_error"]


def test_extract_classifies_execution_error_rows(tmp_path: Path) -> None:
    """Rows with a runtime error become execution_error samples."""
    csv_path = tmp_path / "results.csv"
    _write_csv(
        csv_path,
        [
            _base_row(
                id="E004",
                predicted_route="error",
                predicted_tool="error",
                route_ok="False",
                tool_ok="False",
                pass_fail_summary="error",
                error="429 rate limit",
            ),
        ],
    )

    samples = extract_failure_samples(csv_path)

    assert samples[0].error_types == ["execution_error"]
    assert samples[0].execution_error == "429 rate limit"


def test_extract_skips_passing_rows_and_collects_all_failures(tmp_path: Path) -> None:
    """Mixed CSV: only failing rows are extracted, order preserved."""
    csv_path = tmp_path / "results.csv"
    _write_csv(
        csv_path,
        [
            _base_row(id="E005", refusal_ok="False", pass_fail_summary="fail"),
            _base_row(id="E006"),
            _base_row(id="E007", clarify_ok="False", pass_fail_summary="fail"),
        ],
    )

    samples = extract_failure_samples(csv_path)

    assert [s.sample_id for s in samples] == ["E005", "E007"]
    assert samples[0].error_types == ["refusal_error"]
    assert samples[1].error_types == ["clarification_error"]


def test_extract_missing_file_raises(tmp_path: Path) -> None:
    """A missing CSV path raises FileNotFoundError instead of failing silently."""
    try:
        extract_failure_samples(tmp_path / "nope.csv")
    except FileNotFoundError:
        return
    raise AssertionError("expected FileNotFoundError for missing eval CSV")
