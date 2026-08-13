"""Offline tests for the A6 iteration driver (evals mocked, reflections mocked)."""

from __future__ import annotations

import csv
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from src.improvement.gate import SafetyMetrics
from src.improvement.iteration_driver import (
    FullIterationResult,
    compute_effect_metrics,
    run_full_iteration,
)

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
    """Write a synthetic offline eval result CSV."""
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _fail_row(i: int, error_type_col: str = "route_ok") -> dict[str, str]:
    """Build a failing row with one specific check failing."""
    row = {
        "id": f"E{i}",
        "question": f"问题{i}",
        "expected_route": "kb",
        "predicted_route": "clarify",
        "should_clarify": "False",
        "predicted_clarify": "False",
        "expected_tool": "search_kb",
        "predicted_tool": "none",
        "unsafe": "False",
        "refused": "False",
        "evidence_expected": "True",
        "evidence_present": "False",
        "route_ok": "True",
        "tool_ok": "True",
        "clarify_ok": "True",
        "grounding_ok": "True",
        "refusal_ok": "True",
        "pass_fail_summary": "fail",
        "error": "",
    }
    row[error_type_col] = "False"
    return row


def _pass_row(i: int) -> dict[str, str]:
    """Build a fully passing row."""
    row = _fail_row(i)
    row.update(
        {
            "predicted_route": "kb",
            "predicted_tool": "search_kb",
            "evidence_present": "True",
            "pass_fail_summary": "pass",
        }
    )
    return row


def _safe(rate: float, hallucination: float = 0.0) -> SafetyMetrics:
    """Build uniform safety metrics."""
    return SafetyMetrics(
        injection_refusal_rate=rate,
        jailbreak_refusal_rate=rate,
        oos_refusal_rate=rate,
        hallucination_risk=hallucination,
    )


def _fake_client() -> object:
    """Fake LLM client returning distinct reflection entries per call."""
    counter = {"n": 0}

    def chat_completions_create(**kwargs: object) -> object:
        counter["n"] += 1
        n = counter["n"]
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=(
                            f'{{"situation": "situation-{n}", '
                            f'"action": "action-{n}", '
                            f'"lesson": "lesson-{n}"}}'
                        )
                    )
                )
            ]
        )

    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=chat_completions_create)))


def _fake_offline_eval(rows: list[dict[str, str]]):
    """Patch target for the in-process offline eval runner."""

    def _run(eval_path: str, output_dir: str) -> int:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        _write_csv(out / "offline_eval_results_fake.csv", rows)
        return 0

    return _run


def test_compute_effect_metrics_counts_failures(tmp_path: Path) -> None:
    """Failure count comes from the eval result CSV."""
    csv_path = tmp_path / "results.csv"
    _write_csv(csv_path, [_fail_row(1), _pass_row(2), _fail_row(3, "tool_ok")])

    metrics = compute_effect_metrics(csv_path)

    assert metrics.total_failures == 2
    assert metrics.target_error_fixed == 0


def test_full_iteration_accepts_when_failures_drop(tmp_path: Path) -> None:
    """Baseline 2 failures -> injection 0 failures with safe metrics is accepted."""
    from src.improvement.reflection import ReflectionGenerator

    baseline_csv = tmp_path / "baseline.csv"
    _write_csv(baseline_csv, [_fail_row(1), _fail_row(2)])
    injected_rows = [_pass_row(1), _pass_row(2)]

    generator = ReflectionGenerator(client=_fake_client())
    with patch(
        "src.improvement.iteration_driver._run_offline_eval_in_process",
        return_value=tmp_path / "injected.csv",
    ):
        _write_csv(tmp_path / "injected.csv", injected_rows)
        result = run_full_iteration(
            baseline_csv=str(baseline_csv),
            store_path=str(tmp_path / "exp"),
            max_samples=5,
            safety_before=_safe(1.0),
            safety_after=_safe(1.0),
            generator=generator,
        )

    assert isinstance(result, FullIterationResult)
    assert result.baseline_failures == 2
    assert result.injected_failures == 0
    assert result.stored_entries == 2
    assert result.decision.accepted is True


def test_full_iteration_rejects_when_safety_drops(tmp_path: Path) -> None:
    """Safety regression rejects even with effect improvement."""
    from src.improvement.reflection import ReflectionGenerator

    baseline_csv = tmp_path / "baseline.csv"
    _write_csv(baseline_csv, [_fail_row(1)])
    _write_csv(tmp_path / "injected.csv", [_pass_row(1)])
    generator = ReflectionGenerator(client=_fake_client())

    with patch(
        "src.improvement.iteration_driver._run_offline_eval_in_process",
        return_value=tmp_path / "injected.csv",
    ):
        result = run_full_iteration(
            baseline_csv=str(baseline_csv),
            store_path=str(tmp_path / "exp"),
            max_samples=5,
            safety_before=_safe(1.0),
            safety_after=SafetyMetrics(
                injection_refusal_rate=0.9,
                jailbreak_refusal_rate=1.0,
                oos_refusal_rate=1.0,
                hallucination_risk=0.0,
            ),
            generator=generator,
        )

    assert result.decision.accepted is False
    assert "injection_refusal_rate" in result.decision.safety_regressions


def test_full_iteration_rejects_when_no_failures_fixed(tmp_path: Path) -> None:
    """No improvement is rejected (soft goal requires actual fixes)."""
    from src.improvement.reflection import ReflectionGenerator

    baseline_csv = tmp_path / "baseline.csv"
    _write_csv(baseline_csv, [_fail_row(1)])
    _write_csv(tmp_path / "injected.csv", [_fail_row(1)])
    generator = ReflectionGenerator(client=_fake_client())

    with patch(
        "src.improvement.iteration_driver._run_offline_eval_in_process",
        return_value=tmp_path / "injected.csv",
    ):
        result = run_full_iteration(
            baseline_csv=str(baseline_csv),
            store_path=str(tmp_path / "exp"),
            max_samples=5,
            safety_before=_safe(1.0),
            safety_after=_safe(1.0),
            generator=generator,
        )

    assert result.decision.accepted is False
    assert result.stored_entries == 1


def test_full_iteration_marks_entries_rejected_on_gate_failure(tmp_path: Path) -> None:
    """Gate failure downgrades stored entries to rejected source."""
    from src.improvement.experience_store import ExperienceStore
    from src.improvement.reflection import ReflectionGenerator

    baseline_csv = tmp_path / "baseline.csv"
    _write_csv(baseline_csv, [_fail_row(1)])
    _write_csv(tmp_path / "injected.csv", [_fail_row(1)])
    generator = ReflectionGenerator(client=_fake_client())
    store_path = tmp_path / "exp"

    with patch(
        "src.improvement.iteration_driver._run_offline_eval_in_process",
        return_value=tmp_path / "injected.csv",
    ):
        run_full_iteration(
            baseline_csv=str(baseline_csv),
            store_path=str(store_path),
            max_samples=5,
            safety_before=_safe(1.0),
            safety_after=_safe(1.0),
            generator=generator,
        )

    store = ExperienceStore(path=str(store_path))
    loaded = store.load()
    assert loaded
    assert all(entry.source == "rejected" for entry in loaded)
