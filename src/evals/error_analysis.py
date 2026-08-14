"""Minimal offline eval error analysis for knowledge-ops-agent."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

DEFAULT_RESULTS_DIR = "data/eval_results"


def _to_bool(value: str | None) -> bool:
    """Convert CSV boolean-like strings into Python booleans."""
    return (value or "").strip().lower() == "true"


def find_latest_results_file(results_dir: str = DEFAULT_RESULTS_DIR) -> Path:
    """Return the newest offline evaluation result file in the target directory."""
    directory = Path(results_dir)
    candidates = sorted(
        directory.glob("offline_eval_results_*.csv"),
        key=lambda path: path.stat().st_mtime,
    )
    if not candidates:
        raise FileNotFoundError(f"No offline eval result files found in {directory}")
    return candidates[-1]


def load_results(path: Path) -> list[dict[str, str]]:
    """Load per-sample offline evaluation records from CSV."""
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def summarize_errors(rows: list[dict[str, str]]) -> dict[str, int]:
    """Count the most useful first-pass offline error categories."""
    route_errors = 0
    tool_errors = 0
    missed_clarifications = 0
    missed_refusals = 0
    missing_evidence = 0

    for row in rows:
        if row.get("predicted_route") == "error":
            continue

        if row.get("expected_route") != row.get("predicted_route"):
            route_errors += 1
        if row.get("expected_tool", "none") != row.get("predicted_tool", "none"):
            tool_errors += 1
        if _to_bool(row.get("should_clarify")) and not _to_bool(row.get("predicted_clarify")):
            missed_clarifications += 1
        if _to_bool(row.get("unsafe")) and not _to_bool(row.get("refused")):
            missed_refusals += 1
        if not _to_bool(row.get("evidence_present")):
            missing_evidence += 1

    return {
        "route_errors": route_errors,
        "tool_errors": tool_errors,
        "missed_clarifications": missed_clarifications,
        "missed_refusals": missed_refusals,
        "missing_evidence": missing_evidence,
    }


def print_summary(results_path: Path, rows: list[dict[str, str]]) -> None:
    """Print a compact error analysis summary for manual inspection."""
    stats = summarize_errors(rows)
    print(f"Results file           : {results_path}")
    print(f"Total result rows      : {len(rows)}")
    print("Error analysis summary :")
    print(f"  route 错误数           {stats['route_errors']}")
    print(f"  工具误调用数          {stats['tool_errors']}")
    print(f"  该澄清未澄清数        {stats['missed_clarifications']}")
    print(f"  该拒答未拒答数        {stats['missed_refusals']}")
    print(f"  无 evidence 输出数    {stats['missing_evidence']}")


def _build_parser() -> argparse.ArgumentParser:
    """Create a tiny CLI parser for offline error analysis."""
    parser = argparse.ArgumentParser(
        description="Analyze offline eval result files for knowledge-ops-agent."
    )
    parser.add_argument(
        "--results-file",
        default="",
        help="Optional explicit CSV result file path. If omitted, the newest file in data/eval_results is used.",
    )
    parser.add_argument(
        "--results-dir",
        default=DEFAULT_RESULTS_DIR,
        help="Directory used when auto-selecting the newest result file.",
    )
    return parser


def main() -> None:
    """Load the target result file and print a minimal error summary."""
    parser = _build_parser()
    args = parser.parse_args()

    results_path = Path(args.results_file) if args.results_file else find_latest_results_file(args.results_dir)
    rows = load_results(results_path)
    print_summary(results_path, rows)


if __name__ == "__main__":
    main()
