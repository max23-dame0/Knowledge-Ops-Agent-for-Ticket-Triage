"""A6: automatic improvement loop orchestration.

Pipeline: eval failures (A1) -> reflection (A2) -> experience pool (A3) ->
injection (A4, env toggle) -> regression -> gate decision (A5). The loop
only orchestrates; safety/effect metrics are computed by the eval modules
and passed in by the caller so this module stays free of LLM/route logic.
"""

from __future__ import annotations

import argparse
import sys

from pydantic import BaseModel, Field

from src.evals.failure_extraction import extract_failure_samples
from src.improvement.experience_store import ExperienceStore
from src.improvement.reflection import ReflectionGenerator
from src.improvement.schemas import ExperienceEntry
from src.utils.logging import get_logger

logger = get_logger(__name__)


class IterationResult(BaseModel):
    """Aggregated outcome of one improvement-loop iteration."""

    extracted: int = Field(description="Failure samples extracted from eval results.")
    reflected: int = Field(description="Reflection calls attempted.")
    stored: int = Field(description="New experience entries actually stored (post-dedupe).")
    error: str | None = Field(default=None, description="Failure reason when the iteration aborted.")


def collect_reflect_store(
    eval_result_csv: str,
    store: ExperienceStore | None = None,
    generator: ReflectionGenerator | None = None,
    max_samples: int = 20,
) -> IterationResult:
    """Run the failure -> reflection -> store half of the loop.

    Extracts failure samples from an offline eval result CSV, reflects over
    each with the generator (fallback entries included), and stores new
    entries in the experience pool. Deduplication is enforced by the store.
    """
    active_store = store or ExperienceStore()
    active_generator = generator or ReflectionGenerator()

    samples = extract_failure_samples(eval_result_csv)
    samples = samples[:max_samples]

    stored = 0
    for sample in samples:
        result = active_generator.reflect(sample)
        if result.entry is not None and active_store.add(result.entry):
            stored += 1

    iteration = IterationResult(
        extracted=len(samples),
        reflected=len(samples),
        stored=stored,
        error=None,
    )
    logger.info(
        "improvement_loop | extracted=%s reflected=%s stored=%s",
        iteration.extracted,
        iteration.reflected,
        iteration.stored,
    )
    return iteration


def mark_rejected(store: ExperienceStore, entry: ExperienceEntry) -> None:
    """Persist a gate-rejected entry as a downgraded `rejected` variant."""
    rejected = entry.model_copy(update={"source": "rejected"})
    store.add(rejected)
    logger.info("improvement_loop | entry_rejected | situation=%s", entry.situation[:40])


def _build_parser() -> argparse.ArgumentParser:
    """Create the improvement-loop CLI parser."""
    parser = argparse.ArgumentParser(description="Run one self-improvement loop iteration (PLN-001 A6).")
    parser.add_argument("--eval-result-csv", required=True, help="Offline eval result CSV to mine failures from.")
    parser.add_argument("--store-path", default="data/experience", help="Experience pool directory.")
    parser.add_argument("--max-samples", type=int, default=20, help="Cap on failure samples per iteration.")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the collect-reflect-store half of the loop from the CLI."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    store = ExperienceStore(path=args.store_path)
    result = collect_reflect_store(
        eval_result_csv=args.eval_result_csv,
        store=store,
        generator=None,
        max_samples=args.max_samples,
    )
    print(result.model_dump_json(indent=2))
    return 0 if result.error is None else 1


if __name__ == "__main__":
    sys.exit(main())
