"""Knowledge base search tool definitions backed by the local retrieval module."""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.rag.retrieve import retrieve_kb


class KBSearchResult(BaseModel):
    """A single retrieval hit returned from the local knowledge base."""

    source_title: str = Field(description="The markdown document name that produced the result.")
    passage: str = Field(description="A short passage from the matched knowledge base chunk.")
    score: float = Field(description="A relevance score where higher values are more relevant.")
    low_confidence: bool = Field(
        default=False,
        description="True when the fused score is below the relevance threshold; "
        "the answer should be treated as weakly grounded.",
    )


class KBSearchResponse(BaseModel):
    """Structured output returned by the knowledge base search tool."""

    query: str = Field(description="The original search query.")
    results: list[KBSearchResult] = Field(description="Top ranked knowledge base passages.")



def search_kb(query: str, top_k: int = 3) -> dict[str, object]:
    """Search the local knowledge base and return a tool-friendly structured result."""
    raw_results = retrieve_kb(query=query, top_k=top_k)
    response = KBSearchResponse(
        query=query,
        results=[KBSearchResult(**item) for item in raw_results],
    )
    return response.model_dump()
