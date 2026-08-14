"""Offline unit tests for markdown chunking utilities."""

from __future__ import annotations

from src.rag.chunking import _split_text, chunk_kb_documents


class TestSplitText:
    def test_simple_split(self) -> None:
        text = " ".join(["word"] * 1000)
        chunks = _split_text(text, chunk_size=400, overlap=80)
        assert len(chunks) >= 3
        assert all(len(c) <= 500 for c in chunks)

    def test_short_text_single_chunk(self) -> None:
        chunks = _split_text("short text", chunk_size=400, overlap=80)
        assert chunks == ["short text"]

    def test_empty_text(self) -> None:
        assert _split_text("   ", chunk_size=400, overlap=80) == []

    def test_chunk_size_clamped_to_min(self) -> None:
        chunks = _split_text("a" * 1000, chunk_size=100, overlap=10)
        # All chunks except the trailing remainder are >= 300 chars.
        assert len(chunks) >= 3
        assert all(len(c) >= 300 for c in chunks[:-1])
        assert len(chunks[-1]) >= 1

    def test_overlap_clamped(self) -> None:
        # overlap >= chunk_size should be clamped to chunk_size // 5 without crashing.
        chunks = _split_text("b" * 1000, chunk_size=400, overlap=500)
        assert chunks
        assert all(len(c) <= 400 for c in chunks)


class TestChunkKbDocuments:
    def test_builds_chunks_with_metadata(self, tmp_path) -> None:
        (tmp_path / "vpn_login.md").write_text("# VPN\n\n" + " ".join(["登录失败排查"] * 200), encoding="utf-8")
        (tmp_path / "billing.md").write_text("# Billing\n\n" + " ".join(["退款规则"] * 200), encoding="utf-8")

        chunks = chunk_kb_documents(str(tmp_path))
        assert chunks
        assert all({"chunk_id", "source_title", "text"} <= set(c.keys()) for c in chunks)
        assert {c["source_title"] for c in chunks} == {"vpn_login", "billing"}
        assert all(c["chunk_id"].startswith(f"{c['source_title']}-chunk-") for c in chunks)

    def test_empty_dir_returns_empty(self, tmp_path) -> None:
        assert chunk_kb_documents(str(tmp_path)) == []

    def test_skips_empty_files(self, tmp_path) -> None:
        (tmp_path / "empty.md").write_text("", encoding="utf-8")
        assert chunk_kb_documents(str(tmp_path)) == []
