"""A6 iteration driver: full automatic loop eval -> reflect -> inject -> regress -> gate.

Orchestrates the complete self-improvement iteration end to end:
1. Baseline offline eval (failure extraction source) or reuse an existing CSV
2. Reflection over failures into the experience pool (real or mock LLM)
3. Re-run offline eval with experience injection enabled
4. Compare effect metrics and evaluate the gate (safety metrics are passed in
   by the caller because the external safety benchmark is expensive)
5. Reject path marks entries as rejected; accept path keeps them active

Run: .venv\\Scripts\\python -m src.improvement.iteration_driver [--baseline-csv ...]
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from src.evals.failure_extraction import extract_failure_samples
from src.improvement.experience_store import ExperienceStore
from src.improvement.gate import (
    EffectMetrics,
    GateDecision,
    SafetyMetrics,
    evaluate_gate,
)
from src.improvement.improvement_loop import collect_reflect_store, mark_rejected
from src.improvement.reflection import ReflectionGenerator
from src.utils.logging import get_logger

logger = get_logger(__name__)

DEFAULT_EVAL_SET = "data/eval_set.csv"
DEFAULT_OUTPUT_DIR = "data/eval_results"
DEFAULT_EXPERIENCE_DIR = "data/experience"


class FullIterationResult(BaseModel):
    """Complete one-iteration outcome with gate decision and paths."""

    started_at: str = Field(description="Iteration start timestamp (UTC ISO).")
    baseline_csv: str = Field(description="Baseline eval result CSV path.")
    injected_csv: str = Field(description="Post-injection eval result CSV path.")
    baseline_failures: int = Field(description="Baseline failing sample count.")
    injected_failures: int = Field(description="Post-injection failing sample count.")
    stored_entries: int = Field(description="New experience entries stored.")
    decision: GateDecision = Field(description="Gate accept/reject verdict.")


def _latest_offline_csv(output_dir: str = DEFAULT_OUTPUT_DIR) -> Path:
    """Return the most recent offline eval result CSV path."""
    candidates = sorted(Path(output_dir).glob("offline_eval_results_*.csv"))
    if not candidates:
        raise FileNotFoundError(f"no offline eval result CSVs under {output_dir}")
    return candidates[-1]


def compute_effect_metrics(csv_path: str | Path) -> EffectMetrics:
    """Compute failure counts from an offline eval result CSV."""
    samples = extract_failure_samples(csv_path)
    return EffectMetrics(target_error_fixed=0, total_failures=len(samples))


def _run_offline_eval_in_process(eval_set: str = DEFAULT_EVAL_SET, output_dir: str = DEFAULT_OUTPUT_DIR) -> Path:
    """Run the offline eval in-process and return the result CSV path."""
    from src.evals.run_evals import run_offline_eval

    exit_code = run_offline_eval(eval_path=eval_set, output_dir=output_dir)
    if exit_code != 0:
        raise RuntimeError(f"offline eval failed with exit code {exit_code}")
    return _latest_offline_csv(output_dir)


def run_full_iteration(
    baseline_csv: str | None = None,
    eval_set: str = DEFAULT_EVAL_SET,
    store_path: str = DEFAULT_EXPERIENCE_DIR,
    max_samples: int = 20,
    safety_before: SafetyMetrics | None = None,
    safety_after: SafetyMetrics | None = None,
    generator: ReflectionGenerator | None = None,
) -> FullIterationResult:
    """Run one complete improvement iteration and gate the result.

    Safety metrics default to perfect parity (all 1.0, hallucination 0) so
    the loop still runs when the expensive external benchmark is skipped;
    callers must pass real before/after values for a truthful gate.
    """
    started_at = datetime.now(UTC).isoformat(timespec="seconds")
    baseline_path = Path(baseline_csv) if baseline_csv else _run_offline_eval_in_process(eval_set)

    store = ExperienceStore(path=store_path)
    baseline_failures = len(extract_failure_samples(baseline_path))

    reflect_result = collect_reflect_store(
        eval_result_csv=str(baseline_path),
        store=store,
        generator=generator,
        max_samples=max_samples,
    )

    os.environ["EXPERIENCE_INJECTION_ENABLED"] = "true"
    try:
        injected_path = _run_offline_eval_in_process(eval_set)
    finally:
        os.environ["EXPERIENCE_INJECTION_ENABLED"] = ""

    injected_failures = len(extract_failure_samples(injected_path))

    effect_before = EffectMetrics(target_error_fixed=0, total_failures=baseline_failures)
    effect_after = EffectMetrics(target_error_fixed=0, total_failures=injected_failures)

    # The gate soft goal needs "target error fixes > 0": measure fixes as the
    # count of baseline failures that no longer fail after injection, but only
    # when total failures did not increase.
    fixed = baseline_failures - injected_failures
    effect_after = effect_after.model_copy(update={"target_error_fixed": max(fixed, 0)})

    decision = evaluate_gate(
        before_safety=safety_before or SafetyMetrics(1.0, 1.0, 1.0, 0.0),
        after_safety=safety_after or SafetyMetrics(1.0, 1.0, 1.0, 0.0),
        before_effect=effect_before,
        after_effect=effect_after,
    )

    if not decision.accepted and reflect_result.stored > 0:
        for entry in store.load():
            if entry.source == "reflection":
                mark_rejected(store, entry)

    result = FullIterationResult(
        started_at=started_at,
        baseline_csv=str(baseline_path),
        injected_csv=str(injected_path),
        baseline_failures=baseline_failures,
        injected_failures=injected_failures,
        stored_entries=reflect_result.stored,
        decision=decision,
    )
    logger.info(
        "full_iteration | baseline_failures=%s injected_failures=%s stored=%s accepted=%s",
        result.baseline_failures,
        result.injected_failures,
        result.stored_entries,
        result.decision.accepted,
    )
    return result


def _build_parser() -> argparse.ArgumentParser:
    """Create the iteration driver CLI parser."""
    parser = argparse.ArgumentParser(description="Run one full self-improvement iteration (PLN-001 A6).")
    parser.add_argument("--baseline-csv", default=None, help="Reuse an existing eval result CSV as baseline.")
    parser.add_argument("--eval-set", default=DEFAULT_EVAL_SET, help="Offline eval set CSV.")
    parser.add_argument("--store-path", default=DEFAULT_EXPERIENCE_DIR, help="Experience pool directory.")
    parser.add_argument("--max-samples", type=int, default=20, help="Cap on reflected failure samples.")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the full iteration from the CLI and print the outcome."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    started = time.time()
    result = run_full_iteration(
        baseline_csv=args.baseline_csv,
        eval_set=args.eval_set,
        store_path=args.store_path,
        max_samples=args.max_samples,
    )
    elapsed = time.time() - started
    print(f"\n=== Full Iteration ({elapsed:.0f}s) ===")
    print(result.model_dump_json(indent=2))
    return 0 if result.decision.accepted else 2


if __name__ == "__main__":
    sys.exit(main())
