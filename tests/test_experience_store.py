"""Offline tests for A3 experience store (jsonl persistence, capacity, dedupe, search)."""

from __future__ import annotations

from pathlib import Path

from src.improvement.experience_store import ExperienceStore
from src.improvement.schemas import ExperienceEntry


def _entry(situation: str, action: str = "a", lesson: str = "l") -> ExperienceEntry:
    """Build a minimal experience entry."""
    return ExperienceEntry(situation=situation, action=action, lesson=lesson)


def test_add_and_load_roundtrip(tmp_path: Path) -> None:
    """Entries persist to jsonl and load back in insertion order."""
    store = ExperienceStore(path=str(tmp_path / "exp.jsonl"))

    store.add(_entry("s1"))
    store.add(_entry("s2"))

    loaded = store.load()
    assert [e.situation for e in loaded] == ["s1", "s2"]


def test_duplicate_entries_are_skipped(tmp_path: Path) -> None:
    """Identical situation+action+lesson entries are stored once."""
    store = ExperienceStore(path=str(tmp_path / "exp.jsonl"))

    store.add(_entry("same", "x", "y"))
    store.add(_entry("same", "x", "y"))

    assert len(store.load()) == 1


def test_capacity_evicts_oldest(tmp_path: Path) -> None:
    """Exceeding max_entries evicts the oldest entries first."""
    store = ExperienceStore(path=str(tmp_path / "exp.jsonl"), max_entries=3)

    for i in range(5):
        store.add(_entry(f"s{i}"))

    loaded = store.load()
    assert len(loaded) == 3
    assert [e.situation for e in loaded] == ["s2", "s3", "s4"]


def test_search_returns_ranked_matches(tmp_path: Path) -> None:
    """Keyword search ranks matching entries ahead of irrelevant ones."""
    store = ExperienceStore(path=str(tmp_path / "exp.jsonl"))

    store.add(_entry("VPN 登录失败被误判为澄清"))
    store.add(_entry("退款到账时效问题"))
    store.add(_entry("VPN 凭证无效被误判为工单"))

    hits = store.search("VPN 登录失败", top_k=2)

    assert len(hits) == 2
    assert "VPN" in hits[0].situation


def test_search_no_match_returns_empty(tmp_path: Path) -> None:
    """Queries with no keyword overlap return an empty list."""
    store = ExperienceStore(path=str(tmp_path / "exp.jsonl"))
    store.add(_entry("VPN 登录失败"))

    assert store.search("完全无关的查询词") == []


def test_empty_store_loads_empty(tmp_path: Path) -> None:
    """A missing jsonl file loads as an empty list without raising."""
    store = ExperienceStore(path=str(tmp_path / "nope.jsonl"))
    assert store.load() == []
