"""Embedding encoders: OpenAI-compatible API client with local sentence-transformers fallback.

构建索引与检索共享同一个编码接口，保证向量空间一致。API 模式（如
SiliconFlow BAAI/bge-m3）返回前做 L2 归一化，与 sentence-transformers 默认
normalize_embeddings=True 的语义对齐，使 FAISS L2 距离评分口径不变。
"""

from __future__ import annotations

from typing import Any

import numpy as np

from src.utils.config import EmbeddingSettings, get_embedding_settings
from src.utils.logging import get_logger

logger = get_logger(__name__)

LOCAL_EMBEDDING_MODEL = "all-MiniLM-L6-v2"
DEFAULT_BATCH_SIZE = 32


class EmbeddingClient:
    """Unified encode interface shared by index building and retrieval."""

    model_name: str

    def encode(
        self,
        texts: list[str],
        *,
        convert_to_numpy: bool = True,
        show_progress_bar: bool = False,
    ) -> Any:
        """Encode texts into vectors; signature mirrors SentenceTransformer.encode."""
        raise NotImplementedError


class OpenAIEmbeddingClient(EmbeddingClient):
    """OpenAI-compatible /embeddings client (SiliconFlow bge-m3 etc.)."""

    def __init__(
        self,
        settings: EmbeddingSettings,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> None:
        from openai import OpenAI

        self.model_name = settings.model
        self._client = OpenAI(api_key=settings.api_key, base_url=settings.base_url)
        self._batch_size = batch_size

    def encode(
        self,
        texts: list[str],
        *,
        convert_to_numpy: bool = True,
        show_progress_bar: bool = False,
    ) -> Any:
        """Encode texts via the remote embeddings endpoint, batched and L2-normalized."""
        del show_progress_bar  # remote calls have no progress bar

        if not texts:
            return np.empty((0, 0), dtype="float32") if convert_to_numpy else []

        vectors: list[list[float]] = []
        for start in range(0, len(texts), self._batch_size):
            batch = texts[start : start + self._batch_size]
            response = self._client.embeddings.create(model=self.model_name, input=batch)
            vectors.extend(item.embedding for item in response.data)

        matrix = np.asarray(vectors, dtype="float32")
        # bge-m3 类 API 输出默认未归一化；对齐 sentence-transformers 的
        # normalize_embeddings=True 约定，保持 L2 距离评分可比。
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        matrix = matrix / np.maximum(norms, 1e-12)
        if not convert_to_numpy:
            return matrix.tolist()
        return matrix


class LocalEmbeddingClient(EmbeddingClient):
    """Local sentence-transformers fallback used when no API key is configured."""

    def __init__(self, model_name: str = LOCAL_EMBEDDING_MODEL) -> None:
        from sentence_transformers import SentenceTransformer

        self.model_name = model_name
        self._model = SentenceTransformer(model_name)

    def encode(
        self,
        texts: list[str],
        *,
        convert_to_numpy: bool = True,
        show_progress_bar: bool = False,
    ) -> Any:
        """Encode texts with the local sentence-transformers model."""
        return self._model.encode(
            texts,
            convert_to_numpy=convert_to_numpy,
            show_progress_bar=show_progress_bar,
        )


def resolve_embedding_model_name() -> str:
    """Return the configured API model name or the local default model name."""
    settings = get_embedding_settings()
    if settings is not None:
        return settings.model
    return LOCAL_EMBEDDING_MODEL


def get_embedding_client(model_name: str | None = None) -> EmbeddingClient:
    """Build the API-backed client when configured, else the local model client.

    API 模式以环境配置的 model 为准（忽略传入的 model_name）；本地模式
    使用传入的 model_name 或本地默认模型。
    """
    settings = get_embedding_settings()
    if settings is not None:
        logger.info(
            "embedding_backend=openai_api | model=%s | base_url=%s",
            settings.model,
            settings.base_url,
        )
        return OpenAIEmbeddingClient(settings)
    name = model_name or LOCAL_EMBEDDING_MODEL
    logger.info("embedding_backend=local | model=%s", name)
    return LocalEmbeddingClient(name)
