"""Offline replay runner: evaluate the agent without a live LLM.

Two modes:
- `replay`  : replay golden trace records and assert the deterministic layers
             (guardrail + route + plan) reproduce the recorded decisions.
- `promote` : promote session traces (real LLM runs) into the golden corpus,
             optionally filtered by question substring.

Replay lets CI check decision stability and lets PRs diff behavior per sample
without spending tokens.
"""

from __future__ import annotations

import argparse
import json
from typing import Any

from src.agents.guardrails import evaluate_guardrails
from src.agents.main_agent import _extract_ticket_id, _build_plan
from src.agents.route_fn import decide_route
from src.evals.replay_store import ReplayStore


def replay_one(record: dict[str, Any]) -> dict[str, Any]:
    """Recompute deterministic decisions for one record and compare them."""
    question = str(record.get("question", ""))
    guardrail = evaluate_guardrails(question)
    decision = decide_route(question)
    ticket_id = _extract_ticket_id(question)
    plan = _build_plan(decision, ticket_id is not None)

    comparisons = {
        "question": question,
        "recorded": {
            "guardrail_action": record.get("guardrail", {}).get("action"),
            "guardrail_blocked": record.get("guardrail", {}).get("blocked"),
            "route": record.get("route_fn", {}).get("route"),
            "plan_steps": [
                step.get("tool") for step in record.get("plan", {}).get("steps", [])
            ],
        },
        "replayed": {
            "guardrail_action": guardrail.get("action"),
            "guardrail_blocked": guardrail.get("blocked"),
            "route": decision.route,
            "plan_steps": [step.tool for step in plan.steps],
        },
    }
    comparisons["route_ok"] = comparisons["recorded"]["route"] == comparisons["replayed"]["route"]
    comparisons["guardrail_ok"] = (
        comparisons["recorded"]["guardrail_blocked"] == comparisons["replayed"]["guardrail_blocked"]
    )
    comparisons["plan_ok"] = (
        comparisons["recorded"]["plan_steps"] == comparisons["replayed"]["plan_steps"]
    )
    comparisons["ok"] = comparisons["route_ok"] and comparisons["guardrail_ok"] and comparisons["plan_ok"]
    return comparisons


def run_replay(path: str | None = None, directory: str | None = None) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Replay the golden corpus and return per-sample comparisons + summary."""
    store = ReplayStore(directory=directory or "data/replay")
    records = store.load_golden() if path is None else _load_any_jsonl(path)
    results = [replay_one(record) for record in records]
    summary = {
        "total": len(results),
        "passed": sum(1 for item in results if item.get("ok")),
        "route_mismatch": sum(1 for item in results if not item.get("route_ok")),
        "guardrail_mismatch": sum(1 for item in results if not item.get("guardrail_ok")),
        "plan_mismatch": sum(1 for item in results if not item.get("plan_ok")),
    }
    return results, summary


def promote_sessions(
    question_filter: str | None = None,
    limit: int = 100,
    golden_path: str | None = None,
    directory: str | None = None,
) -> dict[str, int]:
    """Promote session traces into the golden corpus (optional filter/limit)."""
    store = ReplayStore(directory=directory or "data/replay")
    records = store.iter_sessions()
    selected: list[dict[str, Any]] = []
    for record in records:
        if question_filter and question_filter not in str(record.get("question", "")):
            continue
        selected.append(record)
        if len(selected) >= limit:
            break
    store.append_golden(selected, path=golden_path or "golden/samples.jsonl")
    return {"promoted": len(selected), "scanned": len(records)}


def _load_any_jsonl(path: str) -> list[dict[str, Any]]:
    """Load JSONL records from an arbitrary path."""
    from pathlib import Path

    file = Path(path)
    if not file.exists():
        raise FileNotFoundError(f"Replay file not found: {path}")
    return [json.loads(line) for line in file.read_text(encoding="utf-8").splitlines() if line.strip()]


def _build_parser() -> argparse.ArgumentParser:
    """Create the replay CLI parser."""
    parser = argparse.ArgumentParser(description="Replay deterministic agent decisions offline.")
    sub = parser.add_subparsers(dest="command", required=True)

    replay_parser = sub.add_parser("replay", help="Replay the golden corpus.")
    replay_parser.add_argument("--path", default=None, help="Optional JSONL path to replay instead of golden.")

    promote_parser = sub.add_parser("promote", help="Promote session traces into the golden corpus.")
    promote_parser.add_argument("--question-filter", default=None, help="Only promote questions containing this text.")
    promote_parser.add_argument("--limit", type=int, default=100, help="Maximum records to promote.")

    return parser


def main() -> None:
    """Run the replay CLI."""
    args = _build_parser().parse_args()
    if args.command == "replay":
        results, summary = run_replay(args.path)
        for item in results:
            status = "PASS" if item["ok"] else "FAIL"
            print(f"[{status}] {item['question'][:50]} route={item['replayed']['route']}")
        print(json.dumps(summary, ensure_ascii=False))
    elif args.command == "promote":
        summary = promote_sessions(args.question_filter, args.limit)
        print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
