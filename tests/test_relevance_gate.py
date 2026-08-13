"""Offline tests for C2 relevance gating on rerank scores."""

from __future__ import annotations

from src.rag.relevance_gate import (
    DEFAULT_RERANK_THRESHOLD,
    classify_confidence,
    strong_evidence_present,
)


def test_above_threshold_is_strong() -> None:
    """A rerank score at/above the threshold yields strong evidence."""
    assert classify_confidence(0.8) == "strong"
    assert classify_confidence(DEFAULT_RERANK_THRESHOLD) == "strong"


def test_below_threshold_is_weak() -> None:
    """A rerank score below the threshold yields weak evidence."""
    assert classify_confidence(DEFAULT_RERANK_THRESHOLD - 0.01) == "weak"
    assert classify_confidence(0.0) == "weak"


def test_missing_rerank_score_is_weak() -> None:
    """Hits without rerank_score (fallback path) are treated as weak."""
    assert classify_confidence(None) == "weak"


def test_strong_evidence_present_scans_top_hits() -> None:
    """Any hit above threshold marks the retrieval as strongly grounded."""
    hits = [
        {"source_title": "a", "rerank_score": 0.4},
        {"source_title": "b", "rerank_score": 0.85},
    ]
    assert strong_evidence_present(hits) is True


def test_strong_evidence_absent_when_all_weak() -> None:
    """All-weak hits mark the retrieval as weakly grounded."""
    hits = [
        {"source_title": "a", "rerank_score": 0.4},
        {"source_title": "b", "rerank_score": 0.3},
    ]
    assert strong_evidence_present(hits) is False


def test_strong_evidence_empty_hits() -> None:
    """Empty hit list is weakly grounded by definition."""
    assert strong_evidence_present([]) is False
