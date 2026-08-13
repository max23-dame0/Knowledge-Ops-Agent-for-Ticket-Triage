"""Offline tests for A4 experience injection format and toggle behaviour."""

from __future__ import annotations

from pathlib import Path

from src.improvement.experience_store import ExperienceStore
from src.improvement.injection import (
    build_experience_injection,
    injection_enabled,
)
from src.improvement.schemas import ExperienceEntry
from src.tools.experience_retrieval import retrieve_experience


def _entries() -> list[ExperienceEntry]:
    return [
        ExperienceEntry(
            situation="短且模糊的 VPN 问题被误判为需要澄清",
            action="含明确 VPN 关键词的查询直接走知识库检索",
            lesson="主题明确的短问题不应过度澄清",
            target_error_type="route_error",
        ),
        ExperienceEntry(
            situation="升级政策问题被误判为工单查询",
            action="政策类问题优先检索知识库",
            lesson="政策询问与工单查询的边界需要强化",
            target_error_type="route_error",
        ),
    ]


def test_injection_format_is_stable() -> None:
    """Injection text embeds entries with fixed markers and no markdown headers."""
    text = build_experience_injection(_entries())

    assert "历史经验" in text
    assert "situation=" in text
    assert "action=" in text
    assert "lesson=" in text
    assert "##" not in text  # no markdown headers per instructions rule 15
    assert "短且模糊的 VPN 问题" in text


def test_injection_empty_entries_returns_empty() -> None:
    """No entries produce an empty injection string."""
    assert build_experience_injection([]) == ""


def test_injection_enabled_reads_env(monkeypatch) -> None:
    """The toggle defaults off and follows EXPERIENCE_INJECTION_ENABLED."""
    monkeypatch.delenv("EXPERIENCE_INJECTION_ENABLED", raising=False)
    assert injection_enabled() is False
    monkeypatch.setenv("EXPERIENCE_INJECTION_ENABLED", "true")
    assert injection_enabled() is True
    monkeypatch.setenv("EXPERIENCE_INJECTION_ENABLED", "0")
    assert injection_enabled() is False


def test_retrieve_experience_ranks_relevant_entries(tmp_path: Path) -> None:
    """Retrieval returns ranked entries for a matching query."""
    store = ExperienceStore(path=str(tmp_path / "exp.jsonl"))
    for entry in _entries():
        store.add(entry)

    hits = retrieve_experience("VPN 登录失败怎么办", store=store, top_k=2)

    assert len(hits) == 1  # only the VPN entry shares tokens with the query
    assert "VPN" in hits[0].situation


def test_retrieve_experience_no_match(tmp_path: Path) -> None:
    """Unrelated queries retrieve nothing."""
    store = ExperienceStore(path=str(tmp_path / "exp.jsonl"))
    for entry in _entries():
        store.add(entry)

    assert retrieve_experience("打印机卡纸", store=store) == []


def test_injection_never_contains_route_instructions() -> None:
    """Injected experience text must not instruct any route decision (D004)."""
    text = build_experience_injection(_entries())
    for forbidden in ("route=", "路由=", "你必须", "不得"):
        assert forbidden not in text
