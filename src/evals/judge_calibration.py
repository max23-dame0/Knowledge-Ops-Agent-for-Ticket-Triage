"""D2: judge calibration workflow.

Samples kb-route answers from the offline eval set, runs the real agent and
the semantic grader over each, and emits a TSV labeling sheet with the judge
scores pre-filled and three empty columns for human annotation. Agreement is
computed afterwards by compute_agreement().

Run: .venv\\Scripts\\python -m src.evals.judge_calibration [--limit 12]
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from src.agents.main_agent import run_agent
from src.evals.semantic_grader import GradeResult, SemanticGrader
from src.utils.logging import get_logger

logger = get_logger(__name__)

DEFAULT_EVAL_SET = "data/eval_set.csv"
DEFAULT_OUTPUT = "data/judge_calibration_labeling.tsv"

TSV_COLUMNS = [
    "sample_id",
    "question",
    "answer",
    "judge_correctness",
    "judge_completeness",
    "judge_evidence_support",
    "human_correctness",
    "human_completeness",
    "human_evidence_support",
]

SCORE_DIMENSIONS = ("correctness", "completeness", "evidence_support")


def load_kb_samples(eval_set: str = DEFAULT_EVAL_SET, limit: int = 12) -> list[dict[str, str]]:
    """Return the first `limit` kb-route rows from the eval set."""
    path = Path(eval_set)
    if not path.exists():
        raise FileNotFoundError(f"eval set not found: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    kb_rows = [row for row in rows if (row.get("expected_route") or "").strip() == "kb"]
    return kb_rows[:limit]


def _judge_answer(grader: SemanticGrader, row: dict[str, str]) -> tuple[str, GradeResult]:
    """Run the agent once and judge its conclusion."""
    answer = run_agent(row["question"])
    conclusion = answer.conclusion.strip()
    grade = grader.grade(
        sample_id=row.get("id", ""),
        question=row.get("question", ""),
        answer=conclusion,
    )
    return conclusion, grade


def build_labeling_sheet(
    eval_set: str = DEFAULT_EVAL_SET,
    output_path: str = DEFAULT_OUTPUT,
    limit: int = 12,
    grader: SemanticGrader | None = None,
) -> Path:
    """Produce the TSV labeling sheet with judge scores pre-filled."""
    active_grader = grader or SemanticGrader()
    samples = load_kb_samples(eval_set, limit)

    records: list[dict[str, str]] = []
    for index, row in enumerate(samples, start=1):
        logger.info("judge_calibration | sample=%s/%s id=%s", index, len(samples), row.get("id"))
        conclusion, grade = _judge_answer(active_grader, row)
        record: dict[str, str] = {
            "sample_id": row.get("id", ""),
            "question": row.get("question", ""),
            "answer": conclusion,
            "judge_correctness": "",
            "judge_completeness": "",
            "judge_evidence_support": "",
            "human_correctness": "",
            "human_completeness": "",
            "human_evidence_support": "",
        }
        if grade.scores is not None:
            record["judge_correctness"] = str(grade.scores.correctness)
            record["judge_completeness"] = str(grade.scores.completeness)
            record["judge_evidence_support"] = str(grade.scores.evidence_support)
        else:
            logger.warning("judge_calibration | judge_failed id=%s error=%s", row.get("id"), grade.error)
        records.append(record)

    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=TSV_COLUMNS, delimiter="\t")
        writer.writeheader()
        writer.writerows(records)

    logger.info("judge_calibration | wrote=%s samples=%d", out_path, len(records))
    return out_path


def compute_agreement(
    judge_scores: list[dict[str, int] | None],
    human_scores: list[dict[str, int] | None],
    tolerance: int = 0,
) -> float:
    """Return dimension-level agreement between judge and human scores.

    A dimension agrees when |judge - human| <= tolerance across the three
    quality dimensions. Unpaired or missing scores count as disagreement.
    """
    if len(judge_scores) != len(human_scores):
        raise ValueError("judge_scores and human_scores must have the same length")
    total = 0
    agreed = 0
    for judge, human in zip(judge_scores, human_scores):
        if judge is None or human is None:
            total += len(SCORE_DIMENSIONS)
            continue
        for dimension in SCORE_DIMENSIONS:
            total += 1
            if abs(int(judge.get(dimension, 0)) - int(human.get(dimension, 0))) <= tolerance:
                agreed += 1
    if total == 0:
        return 0.0
    return round(agreed / total, 4)


def _build_parser() -> argparse.ArgumentParser:
    """Create the judge calibration CLI parser."""
    parser = argparse.ArgumentParser(description="Build the D2 judge calibration labeling sheet.")
    parser.add_argument("--eval-set", default=DEFAULT_EVAL_SET, help="Offline eval set CSV.")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Output TSV path.")
    parser.add_argument("--limit", type=int, default=12, help="Number of kb samples to judge.")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the calibration sheet builder from the CLI."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    out_path = build_labeling_sheet(
        eval_set=args.eval_set,
        output_path=args.output,
        limit=args.limit,
    )
    print(f"[OK] labeling sheet written: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
