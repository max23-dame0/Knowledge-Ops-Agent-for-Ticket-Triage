"""Knowledge base repository: cached access to the FAISS index and metadata.

Wraps index loading so repeated queries do not re-read the FAISS file and
metadata JSON from disk on every call. refresh() invalidates the cache when
the index is rebuilt.
"""

from __future__ import annotations

import json
import threading
from functools import lru_cache
from pathlib import Path
from typing import Any

DEFAULT_INDEX_PATH = "data/index/kb_index.faiss"
DEFAULT_METADATA_PATH = "data/index/kb_metadata.json"


class KBRepository:
    """Thread-safe repository that caches index + metadata and the embedding model."""

    def __init__(
        self,
        index_path: str = DEFAULT_INDEX_PATH,
        metadata_path: str = DEFAULT_METADATA_PATH,
        model_name: str = "all-MiniLM-L6-v2",
    ) -> None:
        self._index_path = Path(index_path)
        self._metadata_path = Path(metadata_path)
        self._model_name = model_name
        self._lock = threading.RLock()
        self._index = None
        self._metadata: list[dict[str, Any]] | None = None

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def index_path(self) -> Path:
        return self._index_path

    @property
    def metadata_path(self) -> Path:
        return self._metadata_path

    def available(self) -> bool:
        return self._index_path.exists() and self._metadata_path.exists()

    def get_metadata(self) -> list[dict[str, Any]]:
        """Return cached metadata chunks, loading from disk on first access."""
        with self._lock:
            if self._metadata is None:
                if not self._metadata_path.exists():
                    return []
                self._metadata = json.loads(self._metadata_path.read_text(encoding="utf-8-sig"))
            return self._metadata

    def get_index(self):
        """Return the cached FAISS index, loading from disk on first access."""
        import faiss

        with self._lock:
            if self._index is None:
                if not self._index_path.exists():
                    raise FileNotFoundError(f"FAISS index not found: {self._index_path}")
                self._index = faiss.read_index(str(self._index_path))
            return self._index

    def get_embedding_model(self, model_name: str):
        """Return the (module-level cached) sentence-transformers model."""
        return _cached_embedding_model(model_name)

    def refresh(self) -> None:
        """Invalidate cached index and metadata (call after index rebuild)."""
        with self._lock:
            self._index = None
            self._metadata = None
        _cached_embedding_model.cache_clear()


@lru_cache(maxsize=4)
def _cached_embedding_model(model_name: str):
    """Load and cache the sentence-transformers model at module level."""
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name)


# Module-level singleton shared by retrieval callers.
_default_repository = KBRepository()


def get_kb_repository() -> KBRepository:
    """Return the shared knowledge base repository instance."""
    return _default_repository
