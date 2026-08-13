"""C4: retrieval quality benchmark over the KB retrieval eval set.

Metrics (document-level, source_title labels):
- recall@k  : fraction of queries with at least one relevant doc in top-k
- MRR       : mean reciprocal rank of the first relevant doc

Run: .venv\\Scripts\\python -m src.evals.retrieval_bench [--no-rerank]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.utils.logging import get_logger

logger = get_logger(__name__)

DEFAULT_EVAL_SET_PATH = "data/retrieval_eval_set.json"
DEFAULT_OUTPUT_DIR = "data/eval_results"


def load_retrieval_eval_set(path: str = DEFAULT_EVAL_SET_PATH) -> list[dict[str, Any]]:
    """Load the retrieval eval set; raise a clear error on malformed input."""
    eval_path = Path(path)
    if not eval_path.exists():
        raise FileNotFoundError(f"retrieval eval set not found: {eval_path}")
    data = json.loads(eval_path.read_text(encoding="utf-8"))
    items = data.get("items", [])
    for item in items:
        if not item.get("query") or not item.get("relevant_docs"):
            raise ValueError(f"malformed eval item: {item}")
    return items


def recall_at_k(
    queries: list[list[str]],
    relevant_docs: list[list[str]],
    k: int,
) -> float:
    """Return the fraction of queries whose top-k results hit a relevant doc."""
    if not queries:
        return 0.0
    hits = sum(
        1
        for retrieved, relevant in zip(queries, relevant_docs)
        if any(doc in relevant for doc in retrieved[:k])
    )
    return round(hits / len(queries), 4)


def mean_reciprocal_rank(
    queries: list[list[str]],
    relevant_docs: list[list[str]],
) -> float:
    """Return MRR across queries; queries with no hit contribute 0."""
    if not queries:
        return 0.0
    total = 0.0
    for retrieved, relevant in zip(queries, relevant_docs):
        for rank, doc in enumerate(retrieved, start=1):
            if doc in relevant:
                total += 1.0 / rank
                break
    return round(total / len(queries), 4)


def run_bench(
    eval_set_path: str = DEFAULT_EVAL_SET_PATH,
    top_k: int = 5,
    use_rerank: bool = True,
    output_dir: str = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    """Run the retrieval benchmark and write a timestamped report."""
    from src.rag.retrieve import retrieve_kb

    items = load_retrieval_eval_set(eval_set_path)
    retrieved: list[list[str]] = []
    relevant: list[list[str]] = []

    for item in items:
        hits = retrieve_kb(query=item["query"], top_k=top_k, use_rerank=use_rerank)
        retrieved.append([str(hit["source_title"]) for hit in hits])
        relevant.append([str(doc) for doc in item["relevant_docs"]])

    report = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "eval_set": eval_set_path,
        "top_k": top_k,
        "use_rerank": use_rerank,
        "query_count": len(items),
        "recall_at_1": recall_at_k(retrieved, relevant, 1),
        "recall_at_3": recall_at_k(retrieved, relevant, 3),
        "recall_at_5": recall_at_k(retrieved, relevant, 5),
        "mrr": mean_reciprocal_rank(retrieved, relevant),
    }

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    report_path = out_dir / f"retrieval_bench_{stamp}.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.info(
        "retrieval_bench | recall@1=%s recall@3=%s recall@5=%s mrr=%s rerank=%s",
        report["recall_at_1"],
        report["recall_at_3"],
        report["recall_at_5"],
        report["mrr"],
        use_rerank,
    )
    return report


def main() -> int:
    """Run the retrieval benchmark CLI and print the report."""
    parser = argparse.ArgumentParser(description="KB retrieval quality benchmark (PLN-001 C4).")
    parser.add_argument("--eval-set", default=DEFAULT_EVAL_SET_PATH, help="Path to the retrieval eval set JSON.")
    parser.add_argument("--top-k", type=int, default=5, help="Number of retrieved passages per query.")
    parser.add_argument("--no-rerank", action="store_true", help="Disable CrossEncoder rerank for baseline comparison.")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="Report output directory.")
    args = parser.parse_args()

    report = run_bench(
        eval_set_path=args.eval_set,
        top_k=args.top_k,
        use_rerank=not args.no_rerank,
        output_dir=args.output_dir,
    )

    print("\n=== Retrieval Benchmark ===")
    for key, value in report.items():
        print(f"{key:<20}: {value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
