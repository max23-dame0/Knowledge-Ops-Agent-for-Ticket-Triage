"""A2: reflection generator turning failure samples into experience entries.

The generator only produces pattern-level text entries; it has no routing
decision power (ADR D004 red line). All output passes PII sanitization and
LLM failures degrade to a template fallback entry.
"""

from __future__ import annotations

import json
import re
from typing import Any

from src.evals.failure_extraction import FailureSample
from src.improvement.schemas import ExperienceEntry, ReflectionResult
from src.utils.logging import get_logger

logger = get_logger(__name__)

REFLECTION_PROMPT_TEMPLATE = """
你是一名支持 Agent 的行为反思教练。以下是一个评测失败的样本，请反思失败根因并产出一条可复用的经验。

失败样本：
- 用户问题：{question}
- 期望路由：{expected_route}
- 实际路由：{predicted_route}
- 错误类型：{error_types}

要求：
1. 只输出一个 JSON 对象，字段为 situation / action / lesson，全部用中文。
   - situation: 用模式化语言描述失败场景（不要写具体用户、工单号、账号等个人信息）
   - action: 下次遇到类似场景时应采取的行为
   - lesson: 提炼出的教训或根因
2. 不得输出任何原始 PII（姓名、邮箱、电话、身份证、银行卡号等个人信息）。
3. 不要输出解释或 JSON 以外的内容。
""".strip()

#: PII patterns replaced with placeholders before any entry is stored.
PII_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "[EMAIL]"),
    (re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"), "[PHONE]"),
    (re.compile(r"\b\d{17}[\dXx]\b"), "[ID_CARD]"),
    (re.compile(r"\b\d{15,19}\b"), "[CARD]"),
)


def sanitize_pii(text: str) -> str:
    """Replace known PII patterns with bracketed placeholders."""
    cleaned = text
    for pattern, placeholder in PII_PATTERNS:
        cleaned = pattern.sub(placeholder, cleaned)
    return cleaned


def _coerce_entry(content: str, sample: FailureSample) -> ExperienceEntry | None:
    """Parse a model reply into an ExperienceEntry; None when unparseable."""
    cleaned = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL | re.IGNORECASE).strip()
    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if match is None:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None

    situation = sanitize_pii(str(data.get("situation", "")).strip())
    action = sanitize_pii(str(data.get("action", "")).strip())
    lesson = sanitize_pii(str(data.get("lesson", "")).strip())
    if not situation or not action or not lesson:
        return None
    return ExperienceEntry(
        situation=situation,
        action=action,
        lesson=lesson,
        source="reflection",
        target_error_type=(sample.error_types[0] if sample.error_types else ""),
    )


def _fallback_entry(sample: FailureSample) -> ExperienceEntry:
    """Build a template entry when the LLM reflection path fails."""
    error_type = sample.error_types[0] if sample.error_types else "unknown"
    return ExperienceEntry(
        situation=f"问题被错误路由：期望 {sample.expected_route}，实际 {sample.predicted_route}",
        action="结合期望路由的判别特征复核分类，必要时先检索证据再作答",
        lesson=f"该样本暴露了 {error_type} 类错误，需强化相关路由边界的判别",
        source="fallback",
        target_error_type=error_type,
    )


class ReflectionGenerator:
    """Low-budget LLM reflection over failure samples with fallback safety."""

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

    def reflect(self, sample: FailureSample) -> ReflectionResult:
        """Reflect over one failure sample and return a sanitized entry."""
        prompt = REFLECTION_PROMPT_TEMPLATE.format(
            question=sample.question,
            expected_route=sample.expected_route,
            predicted_route=sample.predicted_route,
            error_types=", ".join(sample.error_types) if sample.error_types else "unknown",
        )
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
        except Exception as exc:  # noqa: BLE001 - reflection failure degrades to fallback
            logger.warning("reflection_llm_failure | sample=%s | error=%s", sample.sample_id, exc)
            return ReflectionResult(
                sample_id=sample.sample_id,
                entry=_fallback_entry(sample),
                error=str(exc)[:200],
            )

        entry = _coerce_entry(content, sample)
        if entry is None:
            logger.warning("reflection_unparseable | sample=%s", sample.sample_id)
            return ReflectionResult(
                sample_id=sample.sample_id,
                entry=_fallback_entry(sample),
                error=f"unparseable reflection output: {content[:100]}",
            )

        logger.info(
            "reflection_ok | sample=%s | error_type=%s",
            sample.sample_id,
            entry.target_error_type,
        )
        return ReflectionResult(sample_id=sample.sample_id, entry=entry, error=None)
