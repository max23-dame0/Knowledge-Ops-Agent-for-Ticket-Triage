"""Unified benchmark orchestrator for the enterprise-ticket eval system.

Runs the full evaluation matrix for one model:
  1. Tobi agent-behavior (kb/ticket/escalation tool use)  -- via run_full
  2. Tobi supervised classification (type/priority/queue) -- via run_classify
  3. ITSM routing (label -> ticket/kb)                   -- via run_full

Each step has its own JSONL checkpoint, so a crash resumes with --resume.
After all steps, generates the consolidated benchmark report.

Usage:
  python -m src.evals.ticket_bench.run_benchmark --model deepseek-v4-flash-202605 \
      --workers 8 --reasoning-effort low --base-url <url> --api-key <key>
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.evals.ticket_bench.bench_config import OUTPUT_DIR  # noqa: E402


def _run_module(cmd: list[str], step_name: str) -> bool:
    print(f"\n{'='*60}\n>>> {step_name}\n{'='*60}", flush=True)
    t0 = time.time()
    proc = subprocess.Popen(cmd, cwd=str(ROOT))
    proc.wait()
    ok = proc.returncode == 0
    print(f"\n[run_benchmark] {step_name}: {'OK' if ok else 'FAILED'} "
          f"({time.time()-t0:.0f}s, rc={proc.returncode})", flush=True)
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description="Unified enterprise-ticket benchmark.")
    parser.add_argument("--model", required=True)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--reasoning-effort", default="no_think")
    parser.add_argument("--base-url", default="")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--limit", type=int, default=0, help="cap Tobi classify samples per task (0=all)")
    parser.add_argument("--skip-classify", action="store_true")
    parser.add_argument("--skip-full", action="store_true")
    parser.add_argument("--report-only", action="store_true", help="just regenerate the report")
    args = parser.parse_args()

    if args.report_only:
        from src.evals.ticket_bench.report import render_report
        md, data = render_report([args.model])
        stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        (OUTPUT_DIR / f"benchmark_report_{stamp}.md").write_text(md, encoding="utf-8")
        (OUTPUT_DIR / f"benchmark_report_{stamp}.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(md)
        return 0

    base_url_args = ["--base-url", args.base_url] if args.base_url else []
    api_key_args = ["--api-key", args.api_key] if args.api_key else []

    results: dict[str, bool] = {}

    if not args.skip_full:
        results["full"] = _run_module(
            [sys.executable, "-m", "src.evals.ticket_bench.run_full",
             "--model", args.model, "--workers", str(args.workers),
             "--timeout", str(args.timeout), "--max-retries", "3",
             "--reasoning-effort", args.reasoning_effort] + base_url_args + api_key_args
            + (["--resume"] if args.resume else []),
            f"Tobi 全量行为 + ITSM 路由 ({args.model})")

    if not args.skip_classify:
        limit_args = ["--limit", str(args.limit)] if args.limit else []
        results["classify"] = _run_module(
            [sys.executable, "-m", "src.evals.ticket_bench.run_classify",
             "--model", args.model, "--workers", str(args.workers),
             "--timeout", str(args.timeout),
             "--reasoning-effort", args.reasoning_effort] + base_url_args + api_key_args
            + limit_args + (["--resume"] if args.resume else []),
            f"Tobi 有监督分类 type/priority/queue ({args.model})")

    # 汇总报告
    from src.evals.ticket_bench.report import render_report
    md, data = render_report([args.model])
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    md_path = OUTPUT_DIR / f"benchmark_report_{args.model}_{stamp}.md"
    json_path = OUTPUT_DIR / f"benchmark_report_{args.model}_{stamp}.json"
    md_path.write_text(md, encoding="utf-8")
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(md)
    print(f"\n[run_benchmark] report: {md_path}")
    print(f"[run_benchmark] report: {json_path}")
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
