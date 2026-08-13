"""C2: relevance gating over rerank scores for evidence strength signals."""

from __future__ import annotations

from typing import Any

from src.utils.logging import get_logger

logger = get_logger(__name__)

#: Rerank score threshold: above = strong evidence, below = weak evidence.
DEFAULT_RERANK_THRESHOLD = 0.5


def classify_confidence(rerank_score: float | None) -> str:
    """Classify a rerank score into 'strong' or 'weak' evidence strength."""
    if rerank_score is None:
        return "weak"
    return "strong" if rerank_score >= DEFAULT_RERANK_THRESHOLD else "weak"


def strong_evidence_present(hits: list[dict[str, Any]]) -> bool:
    """Return True when at least one top hit carries strong rerank evidence."""
    return any(
        classify_confidence(hit.get("rerank_score")) == "strong"
        for hit in hits
    )
