"""C1: CrossEncoder rerank with lazy loading, caching, and graceful fallback."""

from __future__ import annotations

import math
from typing import Any

from src.utils.logging import get_logger

logger = get_logger(__name__)

DEFAULT_RERANK_MODEL = "BAAI/bge-reranker-base"


def _sigmoid(logit: float) -> float:
    """Map a raw rerank logit into a [0, 1] relevance probability."""
    return 1.0 / (1.0 + math.exp(-logit))


class Reranker:
    """CrossEncoder reranker that loads the model lazily and degrades safely.

    A callable `scorer` may be injected for tests; production uses the
    sentence-transformers CrossEncoder loaded on first use. Any load or
    inference failure falls back to the original candidate order so the
    retrieval pipeline never hard-fails on the rerank stage.
    """

    def __init__(self, model: str | None = DEFAULT_RERANK_MODEL, scorer: Any | None = None) -> None:
        self._model_name = model
        self._scorer = scorer

    def _load(self) -> Any:
        """Load the CrossEncoder once; raise when unavailable."""
        if self._scorer is not None:
            return self._scorer
        from sentence_transformers import CrossEncoder

        self._scorer = CrossEncoder(self._model_name)
        return self._scorer

    def predict(self, pairs: list[list[str]]) -> list[float]:
        """Return raw logits for (query, passage) pairs; [] on failure."""
        try:
            scorer = self._load()
            raw = scorer.predict(pairs)
            return [float(value) for value in raw]
        except Exception as exc:  # noqa: BLE001 - rerank failure must not break retrieval
            logger.warning("rerank_failure=%s | falling back to fused order", exc)
            return []


def rerank_candidates(
    query: str,
    candidates: list[dict[str, object]],
    top_k: int = 3,
    reranker: Reranker | None = None,
) -> list[dict[str, object]]:
    """Rerank fused candidates with the CrossEncoder and keep top_k.

    Each returned item gains `rerank_score` (sigmoid-normalized, 0-1). On
    rerank failure the original fused order is preserved and `rerank_score`
    is omitted, guaranteeing no regression versus the hybrid baseline.
    """
    if not candidates:
        return []

    if reranker is None:
        reranker = Reranker()

    passages = [str(item.get("passage", "")) for item in candidates]
    logits = reranker.predict([[query, passage] for passage in passages])

    if len(logits) != len(candidates):
        ranked = sorted(
            candidates,
            key=lambda item: float(item.get("score", 0.0)),
            reverse=True,
        )[:top_k]
        for item in ranked:
            item.pop("rerank_score", None)
        return ranked

    scored = sorted(
        zip(candidates, logits),
        key=lambda pair: pair[1],
        reverse=True,
    )
    result: list[dict[str, object]] = []
    for item, logit in scored[:top_k]:
        item["rerank_score"] = round(_sigmoid(logit), 4)
        result.append(item)
    return result
