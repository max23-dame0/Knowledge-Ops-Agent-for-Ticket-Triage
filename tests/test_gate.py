"""Offline tests for A5 self-improvement gating (safety hard gate + effect soft goal)."""

from __future__ import annotations

from src.improvement.gate import (
    EffectMetrics,
    GateDecision,
    SafetyMetrics,
    evaluate_gate,
)


def _safe(rate: float) -> SafetyMetrics:
    """Build safety metrics at a uniform refusal rate (hallucination 0)."""
    return SafetyMetrics(
        injection_refusal_rate=rate,
        jailbreak_refusal_rate=rate,
        oos_refusal_rate=rate,
        hallucination_risk=0.0,
    )


def test_accepts_effective_injection_with_safe_metrics() -> None:
    """Errors fixed > 0 with no safety regression is accepted."""
    decision = evaluate_gate(
        before_safety=_safe(1.0),
        after_safety=_safe(1.0),
        before_effect=EffectMetrics(target_error_fixed=0, total_failures=5),
        after_effect=EffectMetrics(target_error_fixed=2, total_failures=3),
    )

    assert decision.accepted is True
    assert decision.safety_regressions == []
    assert isinstance(decision, GateDecision)


def test_rejects_safety_regression() -> None:
    """Any refusal-rate drop is a hard reject (safety gate)."""
    decision = evaluate_gate(
        before_safety=_safe(1.0),
        after_safety=SafetyMetrics(
            injection_refusal_rate=0.95,  # dropped
            jailbreak_refusal_rate=1.0,
            oos_refusal_rate=1.0,
            hallucination_risk=0.0,
        ),
        before_effect=EffectMetrics(target_error_fixed=0, total_failures=5),
        after_effect=EffectMetrics(target_error_fixed=3, total_failures=2),
    )

    assert decision.accepted is False
    assert "injection" in " ".join(decision.safety_regressions)


def test_blocks_reward_hacking() -> None:
    """Route gains with hallucination risk rising is rejected (anti reward hacking)."""
    decision = evaluate_gate(
        before_safety=_safe(1.0),
        after_safety=SafetyMetrics(
            injection_refusal_rate=1.0,
            jailbreak_refusal_rate=1.0,
            oos_refusal_rate=1.0,
            hallucination_risk=0.1,  # hallucination appeared
        ),
        before_effect=EffectMetrics(target_error_fixed=0, total_failures=5),
        after_effect=EffectMetrics(target_error_fixed=5, total_failures=0),
    )

    assert decision.accepted is False


def test_rejects_increased_total_failures() -> None:
    """Effect soft goal requires total failures not to increase."""
    decision = evaluate_gate(
        before_safety=_safe(1.0),
        after_safety=_safe(1.0),
        before_effect=EffectMetrics(target_error_fixed=0, total_failures=3),
        after_effect=EffectMetrics(target_error_fixed=2, total_failures=5),
    )

    assert decision.accepted is False


def test_rejects_no_effect_without_safety_gain() -> None:
    """Zero fixed errors is rejected: the soft goal is improvement, not parity."""
    decision = evaluate_gate(
        before_safety=_safe(1.0),
        after_safety=_safe(1.0),
        before_effect=EffectMetrics(target_error_fixed=0, total_failures=3),
        after_effect=EffectMetrics(target_error_fixed=0, total_failures=3),
    )

    assert decision.accepted is False
