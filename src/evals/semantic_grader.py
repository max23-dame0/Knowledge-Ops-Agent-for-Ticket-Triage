"""D1: LLM judge for three-dimension answer quality scoring.

The judge complements rule-based metrics (D005): it only scores quality
dimensions (correctness / completeness / evidence support, 1-5) for sampled
kb-route answers and never alters behaviour verdicts (ADR D007).
"""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, Field

from src.utils.logging import get_logger

logger = get_logger(__name__)

GRADE_PROMPT_TEMPLATE = """
你是回答质量评审员。请对以下客服 Agent 的回答在三个维度上打分（每个维度 1-5 分，1 最差 5 最好），
只输出一个 JSON 对象，不要输出任何解释：
- correctness: 回答内容与问题事实是否一致、有无错误
- completeness: 回答是否覆盖了问题的关键方面
- evidence_support: 回答是否有工具证据支撑、是否与证据一致

问题：{question}
回答：{answer}

输出 JSON 格式：{{"correctness": 5, "completeness": 4, "evidence_support": 5}}
""".strip()


class QualityScores(BaseModel):
    """Three-dimension quality scores produced by the judge."""

    correctness: int = Field(description="Factual correctness, 1-5.")
    completeness: int = Field(description="Coverage of key aspects, 1-5.")
    evidence_support: int = Field(description="Groundedness in evidence, 1-5.")


class GradeResult(BaseModel):
    """A single judge verdict for one sampled answer."""

    sample_id: str
    question: str
    scores: QualityScores | None = Field(default=None, description="Scores when judging succeeded.")
    error: str | None = Field(default=None, description="Failure reason when judging failed.")


def _clamp(value: Any, low: int = 1, high: int = 5) -> int:
    """Coerce a numeric score into the [low, high] integer range."""
    try:
        number = int(value)
    except (TypeError, ValueError):
        return low
    return max(low, min(high, number))


class SemanticGrader:
    """LLM judge over sampled answers with fail-safe error handling."""

    def __init__(self, client: Any | None = None, model: str | None = None) -> None:
        self._client = client
        self._model = model

    def _get_client(self) -> Any:
        """Return the injected client or build one from env config."""
        if self._client is not None:
            return self._client
        from src.utils.config import get_openai_client, get_openai_settings

        self._model = get_openai_settings().model
        self._client = get_openai_client()
        return self._client

    def grade(self, sample_id: str, question: str, answer: str) -> GradeResult:
        """Judge one answer; failures become error results, never exceptions."""
        prompt = GRADE_PROMPT_TEMPLATE.format(question=question, answer=answer)
        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=self._model or "unknown",
                messages=[
                    {"role": "system", "content": "你只输出 JSON，不输出解释。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
            )
            content = str(response.choices[0].message.content or "")
            scores = _parse_scores(content)
            if scores is None:
                logger.warning("semantic_grader_unparseable | sample=%s", sample_id)
                return GradeResult(
                    sample_id=sample_id,
                    question=question,
                    scores=None,
                    error=f"unparseable judge output: {content[:100]}",
                )
            logger.info("semantic_grader | sample=%s | scores=%s", sample_id, scores)
            return GradeResult(sample_id=sample_id, question=question, scores=scores, error=None)
        except Exception as exc:  # noqa: BLE001 - judge failure must degrade to an error record
            logger.warning("semantic_grader_failure | sample=%s | error=%s", sample_id, exc)
            return GradeResult(sample_id=sample_id, question=question, scores=None, error=str(exc)[:200])


def _parse_scores(content: str) -> QualityScores | None:
    """Parse the judge JSON reply; return None when it is not parseable."""
    cleaned = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL | re.IGNORECASE).strip()
    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if match is None:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return QualityScores(
        correctness=_clamp(data.get("correctness")),
        completeness=_clamp(data.get("completeness")),
        evidence_support=_clamp(data.get("evidence_support")),
    )
