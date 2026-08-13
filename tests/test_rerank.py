"""Offline tests for C1 CrossEncoder rerank (fake scorer, no real model)."""

from __future__ import annotations

import math

from src.rag.rerank import Reranker, rerank_candidates


def _sigmoid(x: float) -> float:
    """Reference sigmoid used to verify score normalization."""
    return 1.0 / (1.0 + math.exp(-x))


class FakeScorer:
    """Deterministic fake CrossEncoder scoring by passage text."""

    def __init__(self, scores_by_text: dict[str, float]) -> None:
        self._scores = scores_by_text
        self.calls: list[tuple[str, str]] = []

    def predict(self, pairs: list[list[str]]) -> list[float]:
        result: list[float] = []
        for pair in pairs:
            self.calls.append((pair[0], pair[1]))
            result.append(self._scores.get(pair[1], 0.0))
        return result


class ExplodingScorer:
    """Scorer that always raises, used for fallback verification."""

    def predict(self, pairs: list[list[str]]) -> list[float]:
        raise RuntimeError("model unavailable")


def _candidate(text: str, score: float) -> dict[str, object]:
    return {"source_title": text, "passage": text, "score": score}


def test_rerank_reorders_by_rerank_score_and_normalizes() -> None:
    """Higher fake logit ranks first; scores are sigmoid-normalized to 0-1."""
    scorer = FakeScorer({"b": 3.0, "a": 1.0, "c": -1.0})
    reranker = Reranker(model=None, scorer=scorer)
    candidates = [_candidate("a", 0.5), _candidate("b", 0.4), _candidate("c", 0.6)]

    out = rerank_candidates("q", candidates, top_k=2, reranker=reranker)

    assert [c["source_title"] for c in out] == ["b", "a"]
    assert out[0]["rerank_score"] == round(_sigmoid(3.0), 4)
    assert out[0]["score"] == 0.4  # original fused score preserved
    assert 0.0 <= out[0]["rerank_score"] <= 1.0


def test_rerank_truncates_to_top_k() -> None:
    """Only top_k items survive reranking."""
    scorer = FakeScorer({"a": 0.1, "b": 0.2, "c": 0.3, "d": 0.4})
    reranker = Reranker(model=None, scorer=scorer)
    candidates = [_candidate(t, 0.5) for t in ("a", "b", "c", "d")]

    out = rerank_candidates("q", candidates, top_k=3, reranker=reranker)

    assert len(out) == 3


def test_rerank_falls_back_to_fused_order_on_scorer_failure() -> None:
    """Scorer explosion degrades gracefully to original fused ranking."""
    reranker = Reranker(model=None, scorer=ExplodingScorer())
    candidates = [_candidate("a", 0.3), _candidate("b", 0.9), _candidate("c", 0.6)]

    out = rerank_candidates("q", candidates, top_k=2, reranker=reranker)

    assert [c["source_title"] for c in out] == ["b", "c"]
