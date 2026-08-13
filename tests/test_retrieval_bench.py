"""Offline tests for C4 retrieval benchmark metrics and eval set loading."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.evals.retrieval_bench import (
    load_retrieval_eval_set,
    mean_reciprocal_rank,
    recall_at_k,
)


def test_recall_at_k_counts_hit_queries() -> None:
    """Recall counts queries with any relevant doc in top-k."""
    retrieved = [["a", "b", "c"], ["x", "y", "z"], ["m", "n"]]
    relevant = [["c"], ["z"], ["m"]]
    assert recall_at_k(retrieved, relevant, 3) == 1.0
    assert recall_at_k(retrieved, relevant, 1) == round(1 / 3, 4)  # top-1 hits only the 3rd query


def test_recall_at_k_empty_input() -> None:
    """Empty input yields 0.0 without division errors."""
    assert recall_at_k([], [], 3) == 0.0


def test_recall_partial_hits() -> None:
    """Queries missing from top-k are not counted."""
    retrieved = [["a"], ["b"], ["c"]]
    relevant = [["z"], ["b"], ["z"]]
    assert recall_at_k(retrieved, relevant, 1) == round(1 / 3, 4)


def test_mrr_computes_reciprocal_ranks() -> None:
    """MRR averages 1/rank of the first relevant doc per query."""
    retrieved = [["a", "b", "c"], ["x", "y"], ["m"]]
    relevant = [["c"], ["y"], ["nope"]]
    expected = round((1 / 3 + 1 / 2 + 0) / 3, 4)
    assert mean_reciprocal_rank(retrieved, relevant) == expected


def test_mrr_empty_input() -> None:
    """Empty input yields 0.0."""
    assert mean_reciprocal_rank([], []) == 0.0


def test_load_eval_set_from_disk() -> None:
    """The real eval set loads with valid items and non-empty labels."""
    items = load_retrieval_eval_set()
    assert len(items) >= 10
    for item in items:
        assert item["query"]
        assert item["relevant_docs"]
        assert item["id"]


def test_load_missing_file_raises(tmp_path: Path) -> None:
    """A missing eval set raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        load_retrieval_eval_set(str(tmp_path / "missing.json"))


def test_load_malformed_item_raises(tmp_path: Path) -> None:
    """Items without query or labels raise ValueError."""
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"items": [{"id": "X", "query": ""}]}), encoding="utf-8")
    with pytest.raises(ValueError):
        load_retrieval_eval_set(str(bad))
