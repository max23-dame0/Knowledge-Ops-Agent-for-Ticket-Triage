"""Offline unit tests for the retrieval evidence wrapper (search_kb mocked)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

# Heavy dependency guard: the import chain pulls in faiss / sentence-transformers.
# Skip when not installed (minimal local env); CI runs these for real.
pytest.importorskip("faiss")

from src.agents.retrieval_agent import RetrievalAgent, retrieve_evidence

FAKE_RAW = {
    "query": "VPN 登录失败怎么办",
    "results": [
        {"source_title": "vpn_login", "passage": "VPN 登录失败请先检查 token 是否过期。", "score": 0.8},
        {"source_title": "password_reset", "passage": "密码重置流程说明。", "score": 0.5},
    ],
}


class TestRetrievalAgent:
    def test_normalizes_evidence(self) -> None:
        with patch("src.agents.retrieval_agent.search_kb", return_value=FAKE_RAW):
            output = RetrievalAgent().retrieve(query="VPN 登录失败怎么办")

        assert output.query == "VPN 登录失败怎么办"
        assert len(output.results) == 2
        assert output.source_titles == ["vpn_login", "password_reset"]
        assert len(output.normalized_evidence) == 2
        assert "KB source=vpn_login" in output.normalized_evidence[0]
        assert "score=0.800" in output.normalized_evidence[0]

    def test_empty_hits(self) -> None:
        with patch("src.agents.retrieval_agent.search_kb", return_value={"query": "q", "results": []}):
            output = RetrievalAgent().retrieve(query="q")

        assert output.results == []
        assert output.source_titles == []
        assert output.normalized_evidence == []

    def test_convenience_function_shape(self) -> None:
        with patch("src.agents.retrieval_agent.search_kb", return_value=FAKE_RAW):
            result = retrieve_evidence(query="VPN 登录失败怎么办")

        assert set(result.keys()) == {"query", "results", "normalized_evidence", "source_titles"}
