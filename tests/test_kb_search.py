"""Offline unit tests for the KB search tool (retrieve_kb mocked)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

# Heavy dependency guard: the tool's import chain pulls in faiss /
# sentence-transformers. When they are not installed (minimal local env),
# skip this module instead of failing collection. CI installs the full
# requirements.txt and runs these tests for real.
pytest.importorskip("faiss")

from src.tools.kb_search import KBSearchResponse, search_kb

FAKE_HITS = [
    {"source_title": "vpn_login", "passage": "VPN 登录失败排查步骤。", "score": 0.9},
    {"source_title": "refund_policy", "passage": "退款到账时效说明。", "score": 0.6},
]


class TestSearchKb:
    def test_returns_structured_response(self) -> None:
        with patch("src.tools.kb_search.retrieve_kb", return_value=FAKE_HITS):
            result = search_kb(query="VPN 登录失败", top_k=2)

        assert result["query"] == "VPN 登录失败"
        assert len(result["results"]) == 2
        assert result["results"][0]["source_title"] == "vpn_login"
        assert result["results"][0]["score"] == 0.9

    def test_schema_validation(self) -> None:
        with patch("src.tools.kb_search.retrieve_kb", return_value=FAKE_HITS):
            result = search_kb(query="q")
        KBSearchResponse.model_validate(result)

    def test_empty_results(self) -> None:
        with patch("src.tools.kb_search.retrieve_kb", return_value=[]):
            result = search_kb(query="q")
        assert result["results"] == []
