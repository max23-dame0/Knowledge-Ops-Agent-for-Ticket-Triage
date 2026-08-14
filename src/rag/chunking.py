"""Simple markdown chunking utilities for local RAG experiments."""

from __future__ import annotations

from pathlib import Path


def chunk_kb_documents(
    input_dir: str,
    chunk_size: int = 400,
    overlap: int = 80,
) -> list[dict[str, str]]:
    """Read markdown files from a directory and split them into overlapping chunks."""
    chunks: list[dict[str, str]] = []
    base_path = Path(input_dir)

    for file_path in sorted(base_path.glob("*.md")):
        text = file_path.read_text(encoding="utf-8-sig").strip()
        if not text:
            continue

        for index, chunk_text in enumerate(_split_text(text, chunk_size=chunk_size, overlap=overlap), start=1):
            chunks.append(
                {
                    "chunk_id": f"{file_path.stem}-chunk-{index}",
                    "source_title": file_path.stem,
                    "text": chunk_text,
                }
            )

    return chunks


def _split_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split text into fixed-size chunks with a small overlap between neighbors."""
    cleaned = " ".join(text.split())
    if not cleaned:
        return []

    chunk_size = max(chunk_size, 300)
    chunk_size = min(chunk_size, 500)
    overlap = max(overlap, 0)
    if overlap >= chunk_size:
        overlap = max(0, chunk_size // 5)

    chunks: list[str] = []
    step = max(1, chunk_size - overlap)
    start = 0

    while start < len(cleaned):
        end = min(len(cleaned), start + chunk_size)
        chunks.append(cleaned[start:end].strip())
        if end >= len(cleaned):
            break
        start += step

    return chunks
