"""Minimal smoke test runners for retrieval and real LLM agent execution."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.agents.main_agent import build_main_agent, run_agent
from src.rag.build_index import build_kb_index
from src.rag.chunking import chunk_kb_documents
from src.tools.kb_search import search_kb
from src.utils.config import get_openai_settings


DEFAULT_QUERY = "VPN 登录失败提示 token 过期怎么办"



def run_kb_smoke_test(
    input_dir: str = "data/kb_docs",
    output_dir: str = "data/index",
    query: str = DEFAULT_QUERY,
) -> int:
    """Run a minimal end-to-end smoke test for the local KB retrieval pipeline."""
    try:
        docs = sorted(Path(input_dir).glob("*.md"))
        if not docs:
            print(f"[FAIL] No markdown files found in {input_dir}")
            return 1
        print(f"[OK] Loaded {len(docs)} markdown documents from {input_dir}")

        chunks = chunk_kb_documents(input_dir=input_dir)
        if not chunks:
            print("[FAIL] Chunking returned no chunks")
            return 1
        print(f"[OK] Chunking produced {len(chunks)} chunks")

        build_result = build_kb_index(input_dir=input_dir, output_dir=output_dir)
        print(
            "[OK] Built index: "
            f"chunks={build_result['chunk_count']} "
            f"index={build_result['index_path']} "
            f"metadata={build_result['metadata_path']}"
        )

        results = search_kb(query=query, top_k=3).get("results", [])
        if not results:
            print(f"[FAIL] Retrieval returned no results for query: {query}")
            return 1

        top_result = results[0]
        print(
            "[OK] Retrieval returned results: "
            f"top_source={top_result['source_title']} score={top_result['score']}"
        )
        print("[PASS] KB smoke test completed successfully")
        return 0
    except Exception as exc:
        print(f"[FAIL] KB smoke test failed: {exc}")
        return 1



def run_llm_smoke_test(
    query: str = DEFAULT_QUERY,
    input_dir: str = "data/kb_docs",
    output_dir: str = "data/index",
) -> int:
    """Run a minimal smoke test for the real LLM-backed knowledge-base agent."""
    try:
        settings = get_openai_settings()
        masked_key = f"{settings.api_key[:6]}..." if len(settings.api_key) >= 6 else "<set>"
        print(
            "[OK] LLM config loaded: "
            f"model={settings.model} base_url={settings.base_url or '<default>'} api_key={masked_key}"
        )
    except Exception as exc:
        print(f"[FAIL] Config issue: {exc}")
        print("[HINT] Check LLM_API_KEY, LLM_MODEL_ID, and optional LLM_BASE_URL in your environment or .env file.")
        return 1

    try:
        agent = build_main_agent()
        print(f"[OK] Agent created: name={agent.name}")
    except Exception as exc:
        print(f"[FAIL] Agent creation issue: {exc}")
        return 1

    try:
        docs = sorted(Path(input_dir).glob("*.md"))
        if not docs:
            print(f"[FAIL] Index issue: no markdown files found in {input_dir}")
            return 1
        build_result = build_kb_index(input_dir=input_dir, output_dir=output_dir)
        print(
            "[OK] Index ready: "
            f"chunks={build_result['chunk_count']} index={build_result['index_path']}"
        )
    except Exception as exc:
        print(f"[FAIL] Index issue: {exc}")
        return 1

    try:
        tool_result = search_kb(query=query, top_k=1)
        results = tool_result.get("results", [])
        if not results:
            print(f"[FAIL] Tool issue: search_kb returned no results for query: {query}")
            return 1
        print(
            "[OK] Tool call succeeded: "
            f"top_source={results[0]['source_title']} score={results[0]['score']}"
        )
    except Exception as exc:
        print(f"[FAIL] Tool issue: {exc}")
        return 1

    try:
        answer = run_agent(query)
        print(
            "[OK] Agent returned final answer: "
            f"conclusion={answer.conclusion} handoff={answer.should_handoff} confidence={answer.confidence:.2f}"
        )
        print("[PASS] LLM smoke test completed successfully")
        return 0
    except Exception as exc:
        print(f"[FAIL] Agent runtime issue: {exc}")
        return 1



def _build_parser() -> argparse.ArgumentParser:
    """Create a tiny CLI parser for smoke test execution."""
    parser = argparse.ArgumentParser(description="Run retrieval or LLM smoke tests for knowledge-ops-agent.")
    parser.add_argument(
        "--mode",
        choices=["kb", "llm"],
        default="llm",
        help="Smoke test mode: 'kb' for retrieval only, 'llm' for full real-agent validation.",
    )
    parser.add_argument(
        "--query",
        default=DEFAULT_QUERY,
        help="Query used for retrieval and LLM validation.",
    )
    return parser



def main() -> None:
    """Run the selected smoke test and exit with a process status code."""
    parser = _build_parser()
    args = parser.parse_args()

    if args.mode == "kb":
        exit_code = run_kb_smoke_test(query=args.query)
    else:
        exit_code = run_llm_smoke_test(query=args.query)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
