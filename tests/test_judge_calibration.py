"""Offline tests for D2 judge calibration sheet building and agreement metric."""

from __future__ import annotations

import csv
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from src.evals.judge_calibration import (
    TSV_COLUMNS,
    build_labeling_sheet,
    compute_agreement,
    load_kb_samples,
)
from src.evals.semantic_grader import GradeResult, QualityScores, SemanticGrader


def _fake_run_agent(question: str):
    """Fake agent returning a fixed conclusion."""
    return SimpleNamespace(conclusion=f"回答: {question[:20]}")


class _FakeGrader(SemanticGrader):
    """Grader returning deterministic scores derived from the question length."""

    def grade(self, sample_id: str, question: str, answer: str) -> GradeResult:
        value = 1 + (len(question) % 5)
        return GradeResult(
            sample_id=sample_id,
            question=question,
            scores=QualityScores(
                correctness=value,
                completeness=value,
                evidence_support=value,
            ),
            error=None,
        )


def test_load_kb_samples(tmp_path: Path) -> None:
    """Only kb-route rows are loaded, limited to the requested count."""
    eval_set = tmp_path / "eval.csv"
    rows = []
    for i in range(5):
        rows.append(
            {
                "id": f"K{i}",
                "question": f"kb 问题 {i}",
                "expected_route": "kb",
            }
        )
        rows.append(
            {
                "id": f"T{i}",
                "question": f"工单 {i}",
                "expected_route": "ticket",
            }
        )
    with eval_set.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["id", "question", "expected_route"])
        writer.writeheader()
        writer.writerows(rows)

    samples = load_kb_samples(str(eval_set), limit=3)

    assert [s["id"] for s in samples] == ["K0", "K1", "K2"]


def test_build_labeling_sheet_structure(tmp_path: Path) -> None:
    """The sheet has all columns, judge scores filled and human columns blank."""
    eval_set = tmp_path / "eval.csv"
    with eval_set.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["id", "question", "expected_route"])
        writer.writeheader()
        writer.writerow({"id": "E001", "question": "VPN 登录失败怎么办", "expected_route": "kb"})
        writer.writerow({"id": "E002", "question": "退款多久到账", "expected_route": "kb"})

    output = tmp_path / "labeling.tsv"
    with patch("src.evals.judge_calibration.run_agent", side_effect=_fake_run_agent):
        result_path = build_labeling_sheet(
            eval_set=str(eval_set),
            output_path=str(output),
            limit=2,
            grader=_FakeGrader(),
        )

    assert result_path == output
    with output.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file, delimiter="\t")
        assert reader.fieldnames == TSV_COLUMNS
        records = list(reader)
    assert len(records) == 2
    for record in records:
        assert record["judge_correctness"] != ""
        assert record["human_correctness"] == ""
        assert record["human_completeness"] == ""
        assert record["human_evidence_support"] == ""


def test_compute_agreement_exact() -> None:
    """Perfect agreement across dimensions is 1.0."""
    judge = [{"correctness": 5, "completeness": 4, "evidence_support": 3}]
    human = [{"correctness": 5, "completeness": 4, "evidence_support": 3}]
    assert compute_agreement(judge, human) == 1.0


def test_compute_agreement_partial() -> None:
    """One dimension off in three yields 2/3 agreement."""
    judge = [{"correctness": 5, "completeness": 4, "evidence_support": 3}]
    human = [{"correctness": 5, "completeness": 4, "evidence_support": 4}]
    assert compute_agreement(judge, human) == round(2 / 3, 4)


def test_compute_agreement_tolerance() -> None:
    """Tolerance=1 accepts off-by-one dimensions."""
    judge = [{"correctness": 5, "completeness": 4, "evidence_support": 3}]
    human = [{"correctness": 4, "completeness": 4, "evidence_support": 3}]
    assert compute_agreement(judge, human, tolerance=0) == round(2 / 3, 4)
    assert compute_agreement(judge, human, tolerance=1) == 1.0


def test_compute_agreement_missing_scores_count_as_disagreement() -> None:
    """A None judge or human score counts as disagreement, not agreement."""
    judge = [None]
    human = [{"correctness": 5, "completeness": 4, "evidence_support": 3}]
    assert compute_agreement(judge, human) == 0.0


def test_compute_agreement_length_mismatch_raises() -> None:
    """Unequal score lists raise ValueError."""
    try:
        compute_agreement([{}], [{}, {}])
    except ValueError:
        return
    raise AssertionError("expected ValueError")
