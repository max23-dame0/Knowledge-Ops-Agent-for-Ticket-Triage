"""Offline tests for A2 reflection generator (mock LLM, no real endpoint)."""

from __future__ import annotations

import json
from types import SimpleNamespace

from src.evals.failure_extraction import FailureSample
from src.improvement.reflection import (
    REFLECTION_PROMPT_TEMPLATE,
    ReflectionGenerator,
    sanitize_pii,
)
from src.improvement.schemas import ExperienceEntry

VALID_REPLY = json.dumps(
    {
        "situation": "短且模糊的 VPN 问题被误判为需要澄清",
        "action": "含明确 VPN 关键词的查询直接走知识库检索",
        "lesson": "主题明确的短问题不应过度澄清",
    },
    ensure_ascii=False,
)


def _make_client(reply: str, raise_error: bool = False) -> object:
    """Build a fake OpenAI-compatible client returning a fixed completion."""

    def chat_completions_create(**kwargs: object) -> object:
        if raise_error:
            raise RuntimeError("endpoint down")
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=reply))]
        )

    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=chat_completions_create)))


def _sample() -> FailureSample:
    """A representative route_error failure sample."""
    return FailureSample(
        sample_id="E009",
        question="一线支持在什么情况下必须升级给二线",
        expected_route="kb",
        predicted_route="escalation",
        error_types=["route_error"],
        evidence_expected=True,
        evidence_present=False,
        execution_error="",
    )


def test_reflection_produces_valid_entry() -> None:
    """A valid LLM reply yields a schema-legal experience entry."""
    generator = ReflectionGenerator(client=_make_client(VALID_REPLY))

    result = generator.reflect(_sample())

    assert result.error is None
    entry = result.entry
    assert isinstance(entry, ExperienceEntry)
    assert entry.situation
    assert entry.action
    assert entry.lesson
    assert entry.source == "reflection"
    assert entry.target_error_type == "route_error"


def test_reflection_falls_back_on_llm_failure() -> None:
    """LLM exceptions yield a template fallback entry, never a raise."""
    generator = ReflectionGenerator(client=_make_client("", raise_error=True))

    result = generator.reflect(_sample())

    assert result.error is not None
    assert result.entry is not None  # fallback entry still produced
    assert result.entry.source == "fallback"
    assert result.entry.target_error_type == "route_error"


def test_reflection_tolerates_unparseable_output() -> None:
    """Non-JSON LLM output degrades to the fallback entry."""
    generator = ReflectionGenerator(client=_make_client("这不是 JSON"))

    result = generator.reflect(_sample())

    assert result.error is not None
    assert result.entry is not None
    assert result.entry.source == "fallback"


def test_pii_scrubbed_from_reflection_text() -> None:
    """Emails, phone numbers, IDs and card numbers are replaced in entries."""
    reply = json.dumps(
        {
            "situation": "用户 zhang@example.com 手机 13812345678 反馈问题",
            "action": "核验身份证 440301199001011234 与银行卡 6222020200112233",
            "lesson": "不要记录原始联系方式",
        },
        ensure_ascii=False,
    )
    generator = ReflectionGenerator(client=_make_client(reply))

    result = generator.reflect(_sample())

    assert result.entry is not None
    entry = result.entry
    assert "zhang@example.com" not in entry.situation
    assert "13812345678" not in entry.situation
    assert "440301199001011234" not in entry.action
    assert "6222020200112233" not in entry.action
    assert "[EMAIL]" in entry.situation


def test_sanitize_pii_unit() -> None:
    """The sanitizer replaces known PII patterns with placeholders."""
    text = "联系 a.b@corp.com 或 13900000000，证件 110101199003076611"
    cleaned = sanitize_pii(text)
    assert "a.b@corp.com" not in cleaned
    assert "13900000000" not in cleaned
    assert "110101199003076611" not in cleaned
    assert "[EMAIL]" in cleaned
    assert "[PHONE]" in cleaned
    assert "[ID_CARD]" in cleaned


def test_prompt_template_mentions_pii_and_json() -> None:
    """The reflection prompt instructs JSON output and PII-free entries."""
    prompt = REFLECTION_PROMPT_TEMPLATE.format(
        question="q",
        expected_route="kb",
        predicted_route="escalation",
        error_types="route_error",
    )
    assert "situation" in prompt
    assert "JSON" in prompt
    assert "PII" in prompt or "隐私" in prompt or "个人信息" in prompt
