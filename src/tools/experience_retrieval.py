"""A4 retrieval side: fetch similar experience entries for a request.

Lives in the tools layer so agents may import it without touching the
improvement orchestration code; returns text-level entries only.
"""

from __future__ import annotations

from src.improvement.experience_store import ExperienceStore
from src.improvement.schemas import ExperienceEntry
from src.utils.logging import get_logger

logger = get_logger(__name__)

DEFAULT_EXPERIENCE_DIR = "data/experience"


def retrieve_experience(
    query: str,
    top_k: int = 3,
    store: ExperienceStore | None = None,
) -> list[ExperienceEntry]:
    """Return experience entries ranked by similarity to the query."""
    active_store = store or ExperienceStore(path=DEFAULT_EXPERIENCE_DIR)
    hits = active_store.search(query=query, top_k=top_k)
    logger.info(
        "experience_retrieval | query=%s | hits=%d",
        query[:60],
        len(hits),
    )
    return hits
