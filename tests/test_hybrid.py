"""Offline unit tests for the dependency-free BM25 + fusion helpers."""

from __future__ import annotations

import pytest

from src.rag.hybrid import BM25Scorer, fuse_scores, tokenize


class TestTokenize:
    def test_mixed_language(self) -> None:
        tokens = tokenize("VPN 登录失败 how-to 排查")
        assert "vpn" in tokens
        # CJK chars tokenize individually (dependency-free, no segmenter).
        assert "登" in tokens
        assert "录" in tokens
        assert "how" in tokens
        assert "to" in tokens

    def test_empty(self) -> None:
        assert tokenize("") == []
        assert tokenize("   ") == []


class TestBM25Scorer:
    def test_relevant_document_ranks_higher(self) -> None:
        corpus = [
            "VPN 登录失败 token 过期 怎么办",
            "退款 到账 时效 说明",
            "发票 抬头 更正 规则",
        ]
        scorer = BM25Scorer(corpus)
        scores = scorer.score("VPN 登录 token 过期")
        assert scores[0] > scores[1]
        assert scores[0] > scores[2]

    def test_normalized_scores_in_range(self) -> None:
        corpus = ["VPN 登录失败", "退款规则", "发票规则"]
        scorer = BM25Scorer(corpus)
        normalized = scorer.score_normalized("VPN")
        assert all(0.0 <= value <= 1.0 for value in normalized)

    def test_no_match_returns_zeros(self) -> None:
        scorer = BM25Scorer(["中文文档内容"])
        assert scorer.score_normalized("zzzzqqqq") == [0.0]


class TestFuseScores:
    def test_weighted_blend(self) -> None:
        fused = fuse_scores([1.0, 0.5], [0.0, 1.0], vector_weight=0.5)
        assert fused == [0.5, 0.75]

    def test_default_weight(self) -> None:
        fused = fuse_scores([1.0], [1.0])
        assert fused == [1.0]

    def test_length_mismatch_raises(self) -> None:
        with pytest.raises(ValueError):
            fuse_scores([1.0], [1.0, 2.0])

    def test_weight_clamped(self) -> None:
        fused = fuse_scores([1.0], [0.0], vector_weight=5.0)
        assert fused == [1.0]
