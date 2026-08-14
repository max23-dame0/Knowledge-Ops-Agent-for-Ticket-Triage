"""Hybrid retrieval helpers: BM25 keyword scoring + score fusion.

BM25 is implemented dependency-free over the chunk metadata (tokenized into
word/character tokens). Fusion combines the normalized BM25 score with the
cosine-like similarity already produced by the vector index.
"""

from __future__ import annotations

import math
import re
from collections import Counter

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+|[\u4e00-\u9fff]", re.IGNORECASE)


def tokenize(text: str) -> list[str]:
    """Split text into lowercased word tokens (CJK chars kept individually)."""
    return [token.lower() for token in _TOKEN_PATTERN.findall(text or "")]


def _inverse_document_frequencies(documents: list[str]) -> dict[str, float]:
    """Compute log idf for every token across the corpus."""
    doc_count = len(documents)
    if doc_count == 0:
        return {}
    doc_freq: Counter[str] = Counter()
    for doc in documents:
        doc_freq.update(set(tokenize(doc)))
    return {
        token: math.log(1.0 + (doc_count - freq + 0.5) / (freq + 0.5))
        for token, freq in doc_freq.items()
    }


def _bm25_score(
    query_tokens: list[str],
    doc_tokens: list[str],
    idf: dict[str, float],
    doc_len: int,
    avg_doc_len: float,
    k1: float = 1.5,
    b: float = 0.75,
) -> float:
    """Compute the BM25 score for one document given query tokens."""
    if not doc_tokens:
        return 0.0
    term_freq = Counter(doc_tokens)
    score = 0.0
    for token in set(query_tokens):
        freq = term_freq.get(token, 0)
        if freq == 0 or token not in idf:
            continue
        denom = freq + k1 * (1.0 - b + b * doc_len / max(avg_doc_len, 1.0))
        score += idf[token] * freq * (k1 + 1.0) / denom
    return score


class BM25Scorer:
    """Dependency-free BM25 over a fixed corpus of chunk texts."""

    def __init__(self, documents: list[str]) -> None:
        self._docs = [tokenize(doc) for doc in documents]
        self._doc_len = [len(tokens) for tokens in self._docs]
        self._avg_doc_len = sum(self._doc_len) / max(len(self._doc_len), 1)
        self._idf = _inverse_document_frequencies(documents)

    def score(self, query: str) -> list[float]:
        """Return a BM25 score per document (raw, not normalized)."""
        query_tokens = tokenize(query)
        if not query_tokens:
            return [0.0] * len(self._docs)
        return [
            _bm25_score(query_tokens, doc, self._idf, doc_len, self._avg_doc_len)
            for doc, doc_len in zip(self._docs, self._doc_len)
        ]

    def score_normalized(self, query: str) -> list[float]:
        """Return per-document BM25 scores normalized to [0, 1]."""
        raw = self.score(query)
        if not raw:
            return []
        max_score = max(raw)
        if max_score <= 0:
            return [0.0] * len(raw)
        return [value / max_score for value in raw]


def fuse_scores(vector_scores: list[float], bm25_scores: list[float], vector_weight: float = 0.7) -> list[float]:
    """Fuse vector similarity and normalized BM25 scores with a weighted blend.

    Vector scores are expected in [0, 1] (higher = more relevant); BM25 scores
    are normalized in the caller. vector_weight controls the blend ratio.
    """
    if len(vector_scores) != len(bm25_scores):
        raise ValueError("vector_scores and bm25_scores must have the same length")
    weight = max(0.0, min(1.0, vector_weight))
    return [weight * v + (1.0 - weight) * b for v, b in zip(vector_scores, bm25_scores)]
