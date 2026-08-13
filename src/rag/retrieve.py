"""Minimal retrieval helpers for the local knowledge base index."""

from __future__ import annotations

from src.repositories.kb_repository import KBRepository, get_kb_repository

# Heavy dependencies (faiss / numpy / sentence-transformers) are imported
# lazily inside the functions below. This keeps the import chain light so
# agent routing logic can be imported and unit-tested without the RAG stack.

DEFAULT_MODEL_NAME = "all-MiniLM-L6-v2"
DEFAULT_INDEX_PATH = "data/index/kb_index.faiss"
DEFAULT_METADATA_PATH = "data/index/kb_metadata.json"


def retrieve_kb(
    query: str,
    top_k: int = 3,
    index_path: str = DEFAULT_INDEX_PATH,
    metadata_path: str = DEFAULT_METADATA_PATH,
    model_name: str = DEFAULT_MODEL_NAME,
    passage_max_chars: int = 280,
    use_hybrid: bool = True,
    min_score: float = 0.25,
    vector_weight: float = 0.7,
    query_expansion: bool = True,
) -> list[dict[str, object]]:
    """Retrieve the most relevant knowledge base passages for a query.

    Uses the shared KBRepository by default so the FAISS index, metadata, and
    embedding model are loaded once and cached across calls. When a non-default
    index location is requested, an ad-hoc repository is built for that call.

    Hybrid mode (default) blends vector similarity with a dependency-free
    BM25 keyword score and marks weak hits with `low_confidence=True` when the
    fused score is below `min_score`. Rule-based query expansion (C3) is
    applied to the search query by default; the original query is preserved
    in the output contract and explicit queries are never rewritten.
    """
    search_query = query
    if query_expansion:
        from src.rag.query_expansion import expand_query

        search_query = expand_query(query)

    repo = _resolve_repository(index_path, metadata_path, model_name)
    if not repo.available():
        raise FileNotFoundError(
            "Local index files are missing. Expected data/index/kb_index.faiss and data/index/kb_metadata.json."
        )

    metadata = repo.get_metadata()
    if not metadata:
        return []

    import numpy as np

    from src.rag.hybrid import BM25Scorer, fuse_scores

    model = repo.get_embedding_model(model_name)
    query_vector = model.encode([search_query], convert_to_numpy=True, show_progress_bar=False)
    query_vector = np.asarray(query_vector, dtype="float32")

    index = repo.get_index()
    search_k = min(max(top_k * 4, 1), len(metadata))  # oversample for hybrid re-ranking
    distances, indices = index.search(query_vector, search_k)

    vector_scores_by_index: dict[int, float] = {}
    for distance, item_index in zip(distances[0], indices[0]):
        if item_index >= 0:
            vector_scores_by_index[int(item_index)] = 1.0 / (1.0 + float(distance))

    bm25 = None
    if use_hybrid:
        bm25 = BM25Scorer([item["text"] for item in metadata])
        bm25_scores = bm25.score_normalized(search_query)

    candidates: list[tuple[float, int]] = []
    for item_index, vector_score in vector_scores_by_index.items():
        if use_hybrid and bm25 is not None:
            fused = fuse_scores([vector_score], [bm25_scores[item_index]], vector_weight=vector_weight)[0]
        else:
            fused = vector_score
        candidates.append((fused, item_index))
    candidates.sort(key=lambda pair: pair[0], reverse=True)

    results: list[dict[str, object]] = []
    for fused_score, item_index in candidates[:top_k]:
        item = metadata[item_index]
        results.append(
            {
                "source_title": item["source_title"],
                "passage": _truncate_passage(item["text"], passage_max_chars),
                "score": round(fused_score, 4),
                "low_confidence": bool(fused_score < min_score),
            }
        )

    return results


def _resolve_repository(index_path: str, metadata_path: str, model_name: str) -> KBRepository:
    """Return the shared repository for default paths, else an ad-hoc instance."""
    default_repo = get_kb_repository()
    if index_path == DEFAULT_INDEX_PATH and metadata_path == DEFAULT_METADATA_PATH:
        return default_repo
    return KBRepository(index_path=index_path, metadata_path=metadata_path, model_name=model_name)


def _truncate_passage(text: str, max_chars: int) -> str:
    """Trim a passage to a model-friendly length without breaking the interface."""
    cleaned = " ".join(text.split())
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 3].rstrip() + "..."
