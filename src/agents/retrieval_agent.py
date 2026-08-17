"""Retrieval grading layer for KB search and evidence normalization.

Renamed from retrieval_agent: this module is NOT an agent - it owns no
routing decisions. It wraps search_kb, grades evidence quality, and returns
structured output for main-agent and UI consumption.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.tools.kb_search import search_kb


class RetrievalHit(BaseModel):
    """A normalized retrieval hit returned by the retrieval layer."""

    source_title: str = Field(description="Knowledge base source title.")
    passage: str = Field(description="Retrieved passage text.")
    score: float = Field(description="Relevance score from KB retrieval.")
    low_confidence: bool = Field(
        default=False,
        description="True when the hit is below the relevance threshold.",
    )


class RetrievalOutput(BaseModel):
    """Structured retrieval output for main-agent and UI consumption."""

    query: str = Field(description="Original retrieval query.")
    results: list[RetrievalHit] = Field(description="Structured KB hits.")
    normalized_evidence: list[str] = Field(description="Display-ready evidence lines derived from retrieval hits.")
    source_titles: list[str] = Field(description="Unique KB source titles referenced by the hits.")


class RetrievalGrader:
    """Thin retrieval helper that wraps search_kb without owning routing decisions."""

    def retrieve(self, query: str, top_k: int = 3) -> RetrievalOutput:
        """Run KB search and normalize the output into stable evidence fields."""
        raw = search_kb(query=query, top_k=top_k)
        hits = [RetrievalHit(**item) for item in raw.get("results", [])]
        source_titles: list[str] = []
        normalized_evidence: list[str] = []

        for hit in hits:
            if hit.source_title not in source_titles:
                source_titles.append(hit.source_title)
            passage_summary = " ".join(hit.passage.split())[:180].strip()
            if passage_summary:
                normalized_evidence.append(
                    f"KB source={hit.source_title} | score={hit.score:.3f} | passage={passage_summary}"
                )
            else:
                normalized_evidence.append(
                    f"KB source={hit.source_title} | score={hit.score:.3f}"
                )

        return RetrievalOutput(
            query=query,
            results=hits,
            normalized_evidence=normalized_evidence,
            source_titles=source_titles,
        )


def retrieve_evidence(query: str, top_k: int = 3) -> dict[str, object]:
    """Convenience function for callers that want normalized retrieval output."""
    return RetrievalGrader().retrieve(query=query, top_k=top_k).model_dump()


# Compatibility aliases for callers that still import the old names.
RetrievalAgent = RetrievalGrader
