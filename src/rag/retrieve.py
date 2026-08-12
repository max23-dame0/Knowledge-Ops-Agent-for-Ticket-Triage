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
) -> list[dict[str, object]]:
    """Retrieve the most relevant knowledge base passages for a query.

    Uses the shared KBRepository by default so the FAISS index, metadata, and
    embedding model are loaded once and cached across calls. When a non-default
    index location is requested, an ad-hoc repository is built for that call.
    """
    repo = _resolve_repository(index_path, metadata_path, model_name)
    if not repo.available():
        raise FileNotFoundError(
            "Local index files are missing. Expected data/index/kb_index.faiss and data/index/kb_metadata.json."
        )

    metadata = repo.get_metadata()
    if not metadata:
        return []

    import numpy as np

    model = repo.get_embedding_model(model_name)
    query_vector = model.encode([query], convert_to_numpy=True, show_progress_bar=False)
    query_vector = np.asarray(query_vector, dtype="float32")

    index = repo.get_index()
    search_k = min(max(top_k, 1), len(metadata))
    distances, indices = index.search(query_vector, search_k)

    results: list[dict[str, object]] = []
    for distance, item_index in zip(distances[0], indices[0]):
        if item_index < 0:
            continue

        item = metadata[item_index]
        results.append(
            {
                "source_title": item["source_title"],
                "passage": _truncate_passage(item["text"], passage_max_chars),
                "score": round(1.0 / (1.0 + float(distance)), 4),
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
