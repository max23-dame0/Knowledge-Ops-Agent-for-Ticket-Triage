"""Offline tests for the embedding client abstraction (mock API, no heavy model load)."""

from __future__ import annotations

import numpy as np

from src.rag.embedding import (
    LOCAL_EMBEDDING_MODEL,
    OpenAIEmbeddingClient,
    resolve_embedding_model_name,
)


class _FakeEmbeddingsAPI:
    """Fake OpenAI-compatible embeddings endpoint returning fixed vectors."""

    def __init__(self) -> None:
        self.embeddings = self._Embeddings(self)

    class _Embeddings:
        def __init__(self, parent: _FakeEmbeddingsAPI) -> None:
            self._parent = parent

        def create(self, *, model: str, input: list[str]) -> object:
            return type(
                "Resp",
                (),
                {"data": [type("Item", (), {"embedding": [3.0, 4.0]})() for _ in input]},
            )()


def _api_client() -> OpenAIEmbeddingClient:
    """Build an OpenAIEmbeddingClient backed by the fake API."""
    client = OpenAIEmbeddingClient.__new__(OpenAIEmbeddingClient)
    client.model_name = "Pro/BAAI/bge-m3"
    client._batch_size = 32
    client._client = _FakeEmbeddingsAPI()
    return client


def _disable_dotenv(monkeypatch) -> None:
    """Stop load_dotenv from re-reading the local .env so tests control env vars."""
    import src.utils.config as config_module

    monkeypatch.setattr(config_module, "load_dotenv", lambda *a, **k: None)


def test_resolve_model_name_falls_back_local(monkeypatch) -> None:
    """No EMBEDDING_API_KEY resolves to the local default model."""
    _disable_dotenv(monkeypatch)
    monkeypatch.delenv("EMBEDDING_API_KEY", raising=False)
    assert resolve_embedding_model_name() == LOCAL_EMBEDDING_MODEL


def test_resolve_model_name_uses_api_model(monkeypatch) -> None:
    """Configured API key resolves to the API model id."""
    _disable_dotenv(monkeypatch)
    monkeypatch.setenv("EMBEDDING_API_KEY", "sk-test")
    monkeypatch.setenv("EMBEDDING_MODEL_ID", "Pro/BAAI/bge-m3")
    monkeypatch.setenv("EMBEDDING_BASE_URL", "https://api.siliconflow.cn/v1")
    assert resolve_embedding_model_name() == "Pro/BAAI/bge-m3"


def test_openai_client_l2_normalizes_vectors() -> None:
    """Remote vectors are L2-normalized to keep L2 distance scoring stable."""
    client = _api_client()

    matrix = client.encode(["a", "b"])

    norms = np.linalg.norm(matrix, axis=1)
    np.testing.assert_allclose(norms, [1.0, 1.0], rtol=1e-5)


def test_openai_client_returns_python_list_when_requested() -> None:
    """convert_to_numpy=False yields a plain list of lists."""
    client = _api_client()

    result = client.encode(["a"], convert_to_numpy=False)

    assert isinstance(result, list)
    assert isinstance(result[0], list)


def test_openai_client_empty_input() -> None:
    """Empty input yields an empty matrix without calling the API."""
    client = _api_client()

    matrix = client.encode([])

    assert matrix.shape == (0, 0)
