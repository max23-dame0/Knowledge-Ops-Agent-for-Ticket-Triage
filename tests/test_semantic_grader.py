"""Offline tests for D1 semantic grader (mock LLM client, no real endpoint)."""

from __future__ import annotations

import json
from types import SimpleNamespace

from src.evals.semantic_grader import (
    GRADE_PROMPT_TEMPLATE,
    GradeResult,
    QualityScores,
    SemanticGrader,
)


def _make_client(reply: str, raise_error: bool = False) -> object:
    """Build a fake OpenAI-compatible client returning a fixed completion."""

    def chat_completions_create(**kwargs: object) -> object:
        if raise_error:
            raise RuntimeError("endpoint down")
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=reply),
                )
            ]
        )

    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=chat_completions_create)))


VALID_REPLY = json.dumps(
    {"correctness": 5, "completeness": 4, "evidence_support": 5},
    ensure_ascii=False,
)


def test_grade_parses_valid_scores() -> None:
    """A valid JSON reply yields normalized 1-5 scores."""
    grader = SemanticGrader(client=_make_client(VALID_REPLY))

    result = grader.grade(
        sample_id="E001",
        question="VPN 登录失败提示 token 过期怎么办",
        answer="请重新登录并检查时间同步。",
    )

    assert isinstance(result, GradeResult)
    assert result.sample_id == "E001"
    assert result.scores == QualityScores(correctness=5, completeness=4, evidence_support=5)
    assert result.error is None


def test_grade_clamps_scores_into_range() -> None:
    """Out-of-range scores are clamped to the 1-5 scale."""
    reply = json.dumps({"correctness": 99, "completeness": 0, "evidence_support": -3})
    grader = SemanticGrader(client=_make_client(reply))

    result = grader.grade("E002", "q", "a")

    assert result.scores == QualityScores(correctness=5, completeness=1, evidence_support=1)


def test_grade_invalid_json_falls_back_to_error() -> None:
    """A non-JSON reply yields an error result instead of raising."""
    grader = SemanticGrader(client=_make_client("完全不是 JSON 的回答"))

    result = grader.grade("E003", "q", "a")

    assert result.scores is None
    assert result.error is not None


def test_grade_endpoint_failure_yields_error() -> None:
    """An endpoint exception yields an error result instead of raising."""
    grader = SemanticGrader(client=_make_client("", raise_error=True))

    result = grader.grade("E004", "q", "a")

    assert result.scores is None
    assert result.error is not None


def test_prompt_template_contains_three_dimensions() -> None:
    """The judge prompt asks for the three quality dimensions explicitly."""
    prompt = GRADE_PROMPT_TEMPLATE.format(
        question="q",
        answer="a",
    )
    for dimension in ("correctness", "completeness", "evidence_support"):
        assert dimension in prompt
