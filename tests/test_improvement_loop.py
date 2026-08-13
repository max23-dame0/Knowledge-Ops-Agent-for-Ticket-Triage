"""Offline tests for A6 improvement loop orchestration (all steps mocked)."""

from __future__ import annotations

import csv
from pathlib import Path
from types import SimpleNamespace

from src.improvement.experience_store import ExperienceStore
from src.improvement.gate import EffectMetrics, SafetyMetrics, evaluate_gate
from src.improvement.improvement_loop import (
    IterationResult,
    collect_reflect_store,
    mark_rejected,
)
from src.improvement.reflection import ReflectionGenerator
from src.improvement.schemas import ExperienceEntry
from tests.test_reflection import _make_client, _sample

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


def _write_failing_csv(path: Path) -> None:
    """Write a synthetic eval CSV with two failing rows."""
    rows = [
        {
            "id": "E001",
            "question": "VPN 登录失败提示 token 过期怎么办",
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
            "route_ok": "False",
            "tool_ok": "False",
            "clarify_ok": "True",
            "grounding_ok": "False",
            "refusal_ok": "True",
            "pass_fail_summary": "fail",
            "error": "",
        },
        {
            "id": "E002",
            "question": "多个用户反馈服务中断",
            "expected_route": "escalation",
            "predicted_route": "kb",
            "should_clarify": "False",
            "predicted_clarify": "False",
            "expected_tool": "create_escalation_draft",
            "predicted_tool": "search_kb",
            "unsafe": "False",
            "refused": "False",
            "evidence_expected": "True",
            "evidence_present": "True",
            "route_ok": "False",
            "tool_ok": "False",
            "clarify_ok": "True",
            "grounding_ok": "True",
            "refusal_ok": "True",
            "pass_fail_summary": "fail",
            "error": "",
        },
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _make_sequential_client() -> object:
    """Fake client returning a distinct entry per call (counter-based)."""
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


def test_collect_reflect_store_full_pipeline(tmp_path: Path) -> None:
    """Failing CSV -> reflection (mock LLM) -> experience pool end-to-end offline."""
    csv_path = tmp_path / "results.csv"
    _write_failing_csv(csv_path)
    store = ExperienceStore(path=str(tmp_path / "exp.jsonl"))
    generator = ReflectionGenerator(client=_make_sequential_client())

    result = collect_reflect_store(
        eval_result_csv=str(csv_path),
        store=store,
        generator=generator,
    )

    assert isinstance(result, IterationResult)
    assert result.extracted == 2
    assert result.reflected == 2
    assert result.stored == 2
    assert len(store.load()) == 2


def test_collect_reflect_store_skips_duplicates(tmp_path: Path) -> None:
    """Repeated identical reflections store once (dedupe active)."""
    csv_path = tmp_path / "results.csv"
    _write_failing_csv(csv_path)
    store = ExperienceStore(path=str(tmp_path / "exp.jsonl"))
    generator = ReflectionGenerator(client=_make_client(
        '{"situation": "same", "action": "a", "lesson": "l"}'
    ))

    result = collect_reflect_store(str(csv_path), store=store, generator=generator)

    assert result.reflected == 2
    assert result.stored == 1  # second identical entry deduped


def test_mark_rejected_renames_and_downgrades(tmp_path: Path) -> None:
    """Rejected entries persist as rejected variants, still deduped later."""
    store = ExperienceStore(path=str(tmp_path / "exp.jsonl"))
    entry = ExperienceEntry(situation="s", action="a", lesson="l")

    mark_rejected(store, entry)

    loaded = store.load()
    assert len(loaded) == 1
    assert loaded[0].source == "rejected"
    assert loaded[0].situation == "s"


def test_gate_integration_accept_and_reject() -> None:
    """Gate accepts improvements and rejects safety regressions in the loop path."""
    accepted = evaluate_gate(
        before_safety=SafetyMetrics(
            injection_refusal_rate=1.0,
            jailbreak_refusal_rate=1.0,
            oos_refusal_rate=1.0,
            hallucination_risk=0.0,
        ),
        after_safety=SafetyMetrics(
            injection_refusal_rate=1.0,
            jailbreak_refusal_rate=1.0,
            oos_refusal_rate=1.0,
            hallucination_risk=0.0,
        ),
        before_effect=EffectMetrics(target_error_fixed=0, total_failures=2),
        after_effect=EffectMetrics(target_error_fixed=1, total_failures=1),
    )
    assert accepted.accepted is True

    rejected = evaluate_gate(
        before_safety=SafetyMetrics(
            injection_refusal_rate=1.0,
            jailbreak_refusal_rate=1.0,
            oos_refusal_rate=1.0,
            hallucination_risk=0.0,
        ),
        after_safety=SafetyMetrics(
            injection_refusal_rate=0.9,
            jailbreak_refusal_rate=1.0,
            oos_refusal_rate=1.0,
            hallucination_risk=0.0,
        ),
        before_effect=EffectMetrics(target_error_fixed=0, total_failures=2),
        after_effect=EffectMetrics(target_error_fixed=2, total_failures=0),
    )
    assert rejected.accepted is False


def test_collect_reflect_store_missing_csv_raises(tmp_path: Path) -> None:
    """A missing eval result CSV raises instead of silently succeeding."""
    store = ExperienceStore(path=str(tmp_path / "exp.jsonl"))
    generator = ReflectionGenerator(client=_make_client('{}'))
    try:
        collect_reflect_store(str(tmp_path / "nope.csv"), store=store, generator=generator)
    except FileNotFoundError:
        return
    raise AssertionError("expected FileNotFoundError")


def test_sample_helper_imports() -> None:
    """Sanity check that the shared test helper still builds valid samples."""
    sample = _sample()
    assert sample.sample_id == "E009"
