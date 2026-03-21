"""Minimal retrieval helpers for the local knowledge base index."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer


@lru_cache(maxsize=1)
def _get_embedding_model(model_name: str) -> SentenceTransformer:
    """Load and cache the sentence-transformers model for repeated local queries."""
    return SentenceTransformer(model_name)


def retrieve_kb(
    query: str,
    top_k: int = 3,
    index_path: str = "data/index/kb_index.faiss",
    metadata_path: str = "data/index/kb_metadata.json",
    model_name: str = "all-MiniLM-L6-v2",
    passage_max_chars: int = 280,
) -> list[dict[str, object]]:
    """Retrieve the most relevant knowledge base passages for a query."""
    index_file = Path(index_path)
    metadata_file = Path(metadata_path)

    if not index_file.exists() or not metadata_file.exists():
        raise FileNotFoundError(
            "Local index files are missing. Expected data/index/kb_index.faiss and data/index/kb_metadata.json."
        )

    metadata = json.loads(metadata_file.read_text(encoding="utf-8-sig"))
    if not metadata:
        return []

    model = _get_embedding_model(model_name)
    query_vector = model.encode([query], convert_to_numpy=True, show_progress_bar=False)
    query_vector = np.asarray(query_vector, dtype="float32")

    index = faiss.read_index(str(index_file))
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


def _truncate_passage(text: str, max_chars: int) -> str:
    """Trim a passage to a model-friendly length without breaking the interface."""
    cleaned = " ".join(text.split())
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 3].rstrip() + "..."
