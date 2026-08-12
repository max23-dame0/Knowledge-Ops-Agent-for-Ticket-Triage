"""Minimal FAISS index builder for local knowledge base documents."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.rag.chunking import chunk_kb_documents


def build_kb_index(
    input_dir: str = "data/kb_docs",
    output_dir: str = "data/index",
    model_name: str = "all-MiniLM-L6-v2",
    chunk_size: int = 400,
    overlap: int = 80,
) -> dict[str, Any]:
    """Build a local FAISS index and metadata files from markdown knowledge base documents."""
    import faiss
    import numpy as np
    from sentence_transformers import SentenceTransformer

    chunks = chunk_kb_documents(input_dir=input_dir, chunk_size=chunk_size, overlap=overlap)
    if not chunks:
        raise ValueError(f"No markdown chunks were created from: {input_dir}")

    model = SentenceTransformer(model_name)
    texts = [chunk["text"] for chunk in chunks]
    embeddings = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
    vectors = np.asarray(embeddings, dtype="float32")

    index = faiss.IndexFlatL2(vectors.shape[1])
    index.add(vectors)

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    index_path = output_path / "kb_index.faiss"
    metadata_path = output_path / "kb_metadata.json"

    faiss.write_index(index, str(index_path))
    metadata_path.write_text(
        json.dumps(chunks, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {
        "index_path": str(index_path),
        "metadata_path": str(metadata_path),
        "chunk_count": len(chunks),
        "embedding_dim": int(vectors.shape[1]),
        "model_name": model_name,
    }


def main() -> None:
    """Build the local knowledge base index using default paths."""
    result = build_kb_index()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
