"""Full-scale ticket benchmark runner for cloud hosts (Tobi 20k + ITSM 900).

Concurrency design (validated on a 32GB Windows box, tuned for 64GB cloud):
- Each model runs as its own process; both are launched in parallel.
- Thread pool with --workers per model. Every in-flight request spawns one
  knot-cli subprocess inside the proxy, so total knot-cli procs =
  workers_hy3 + workers_glm. Memory guideline: knot-cli ~1.5GB each,
  so workers_total <= (RAM_GB - 8) / 1.5.
- Per-request timeout (--timeout, default 30s). Timed-out/failed requests are
  marked, pushed back to the END of the queue, and retried (--max-retries).
- Checkpoint: every result is appended to a JSONL checkpoint file, so a crash
  resumes from the last checkpoint (--resume).
- Progress: prints a line every --report-every completed requests.

Usage (cloud, 64GB):
  # terminal 1
  python -m src.evals.ticket_bench.run_full --model hy3 --workers 18 --timeout 30
  # terminal 2
  python -m src.evals.ticket_bench.run_full --model glm-5.2 --workers 18 --timeout 30
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import hashlib
import json
import queue
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.evals.ticket_bench.bench_core import (
    BASE_URL,
    get_baseline_prompt_tokens,
    load_itsm,
    load_tobi,
    single_call,
)

OUTPUT_DIR = Path("data/eval_results")


def run_full_dataset(
    model: str,
    dataset: str,
    workers: int,
    timeout: float,
    max_retries: int,
    checkpoint_path: Path,
    resume: bool,
    report_every: int = 100,
    reasoning_effort: str = "high",
    base_url: str = "",
    api_key: str = "",
) -> dict[str, Any]:
    if dataset == "tobi":
        samples = load_tobi(0)  # full 20k pool
    else:
        samples = load_itsm(0)  # all 900
    total = len(samples)
    print(f"[{dataset}] loaded {total} samples", flush=True)

    baseline = get_baseline_prompt_tokens(model, base_url=base_url, reasoning_effort=reasoning_effort,
                                          api_key=api_key)
    print(f"[{dataset}] baseline_prompt_tokens={baseline}", flush=True)

    done_results: list[dict[str, Any]] = []
    done_ids: set[tuple[int, int]] = set()
    if resume and checkpoint_path.exists():
        for line in checkpoint_path.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue  # skip corrupt checkpoint lines
            if not r.get("ok"):
                continue  # skip failed rows so they get retried
            try:
                done_results.append(r)
                done_ids.add(tuple(r["sample_id"]))
            except (KeyError, TypeError):
                continue
        print(f"[{dataset}] resumed with {len(done_results)} completed (failed rows will retry)", flush=True)

    pending: queue.Queue[tuple[dict[str, Any], int, tuple[int, str]]] = queue.Queue()
    for idx, s in enumerate(samples):
        sid = (idx, hashlib.md5(s["text"][:80].encode("utf-8")).hexdigest())
        if sid in done_ids:
            continue
        pending.put((s, 0, sid))

    stats = {
        "ok": 0, "timeout": 0, "failed": 0, "retries_used": 0,
        "latencies": [], "prompt_tokens": [], "completion_tokens": [],
        "tool_calls_all": [], "content_lens": [], "types": [],
    }
    stats_lock = threading.Lock()
    checkpoint_lock = threading.Lock()
    last_report = {"count": 0}
    t0 = time.time()

    def worker_loop():
        while True:
            try:
                sample, retry, sid = pending.get_nowait()
            except queue.Empty:
                return
            try:
                r = single_call(model, sample, retries=0, timeout=timeout, base_url=base_url,
                                reasoning_effort=reasoning_effort, api_key=api_key)
            except Exception as exc:  # noqa: BLE001
                r = {"ok": False, "error": f"exc:{exc}", "latency": timeout, "tool_calls": [],
                     "prompt_tokens": 0, "completion_tokens": 0, "content_len": 0}
            is_timeout = (
                not r["ok"]
                and ("timed out" in str(r.get("error", "")).lower() or "timeout" in str(r.get("error", "")).lower())
            )
            if not r["ok"] and retry < max_retries:
                with stats_lock:
                    stats["timeout" if is_timeout else "failed"] += 1
                    stats["retries_used"] += 1
                pending.put((sample, retry + 1, sid))
                continue
            if not r["ok"]:
                with stats_lock:
                    stats["failed"] += 1
                rec = {
                    "sample_id": sid, "ok": False, "error": str(r.get("error", "")),
                    "latency": r.get("latency", 0), "text": sample["text"][:100],
                }
            else:
                with stats_lock:
                    stats["ok"] += 1
                    stats["latencies"].append(r["latency"])
                    stats["prompt_tokens"].append(r["prompt_tokens"])
                    stats["completion_tokens"].append(r["completion_tokens"])
                    stats["tool_calls_all"].append(r["tool_calls"])
                    stats["content_lens"].append(r["content_len"])
                    stats["types"].append(sample.get("type", ""))
                    last_report["count"] += 1
                    if last_report["count"] % report_every == 0:
                        elapsed = time.time() - t0
                        rate = last_report["count"] / max(elapsed, 1)
                        eta = (total - last_report["count"]) / max(rate, 0.001) / 3600
                        print(
                            f"[{dataset}] {last_report['count']}/{total} ok, "
                            f"rate={rate:.1f}/s ETA={eta:.1f}h",
                            flush=True,
                        )
                rec = {
                    "sample_id": sid, "ok": True, "error": None,
                    "latency": r["latency"], "tool_calls": r["tool_calls"],
                    "prompt_tokens": r["prompt_tokens"], "completion_tokens": r["completion_tokens"],
                    "content_len": r["content_len"],
                    "type": sample.get("type", ""), "text": sample["text"][:100],
                }
            with checkpoint_lock, checkpoint_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            done_results.append(rec)

    with cf.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(worker_loop) for _ in range(workers)]
        for fut in cf.as_completed(futures):
            fut.result()
    wall = time.time() - t0

    ok_rows = [r for r in done_results if r["ok"]]
    lat = sorted(r["latency"] for r in ok_rows)

    def pct(p: float) -> float:
        if not lat:
            return 0.0
        return round(lat[min(len(lat) - 1, int(p * len(lat)))], 2)

    total_prompt = sum(r["prompt_tokens"] for r in ok_rows)
    total_comp = sum(r["completion_tokens"] for r in ok_rows)
    delta_prompt = sum(max(r["prompt_tokens"] - baseline, 0) for r in ok_rows)

    quality: dict[str, Any] = {}
    if dataset == "itsm":
        def route_of(r: dict[str, Any]) -> str:
            return "ticket" if any("ticket" in t for t in r["tool_calls"]) else "kb"
        correct = sum(1 for r in ok_rows if route_of(r) == r.get("expected", "kb"))
        quality["route_accuracy"] = round(correct / max(len(ok_rows), 1), 4)
    else:
        kb_calls = sum(1 for r in ok_rows if any("search_kb" in t for t in r["tool_calls"]))
        esc_calls = sum(1 for r in ok_rows if any("escalation" in t for t in r["tool_calls"]))
        quality["kb_grounding_rate"] = round(kb_calls / max(len(ok_rows), 1), 4)
        quality["escalation_signal_rate"] = round(esc_calls / max(len(ok_rows), 1), 4)
        quality["answerable_rate"] = round(
            sum(1 for r in ok_rows if r.get("content_len", 0) > 0 or r["tool_calls"]) / max(len(ok_rows), 1), 4)

    return {
        "dataset": dataset,
        "model": model,
        "workers": workers,
        "timeout": timeout,
        "total": total,
        "ok_count": len(ok_rows),
        "success_rate": round(len(ok_rows) / max(total, 1), 4),
        "timeout_count": stats["timeout"],
        "failed_count": stats["failed"],
        "retries_used": stats["retries_used"],
        **quality,
        "wall_seconds": round(wall, 2),
        "throughput_rps": round(len(ok_rows) / wall, 3) if wall > 0 else 0,
        "latency_p50": pct(0.50),
        "latency_p95": pct(0.95),
        "latency_p99": pct(0.99),
        "latency_max": round(max(lat), 2) if lat else 0,
        "baseline_prompt_tokens": baseline,
        "total_prompt_tokens": total_prompt,
        "total_completion_tokens": total_comp,
        "delta_prompt_tokens": delta_prompt,
        "delta_total_tokens": delta_prompt + total_comp,
        "avg_delta_tokens_per_req": round((delta_prompt + total_comp) / max(len(ok_rows), 1), 1),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Full-scale ticket benchmark (cloud).")
    parser.add_argument("--model", required=True,
                        choices=["glm-5.2", "hy3", "deepseek-v4-flash", "deepseek-v4-pro-202606",
                                 "deepseek-v4-flash-202605", "gemini-3.7-flash-high"])
    parser.add_argument("--workers", type=int, default=18, help="concurrent requests (each spawns one knot-cli)")
    parser.add_argument("--timeout", type=float, default=30.0, help="per-request timeout seconds")
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--resume", action="store_true", help="resume from checkpoint")
    parser.add_argument("--report-every", type=int, default=100)
    parser.add_argument("--reasoning-effort", default="high",
                        help="reasoning effort for the model (e.g. high/low/no_think; hy3 supports no_think)")
    parser.add_argument("--base-url", default=BASE_URL, help="custom OpenAI-compatible base URL (default: knot-proxy)")
    parser.add_argument("--api-key", default="", help="API key for the base URL (optional)")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    results: dict[str, Any] = {}

    for dataset in ("tobi", "itsm"):
        ckpt = OUTPUT_DIR / f"ticket_full_{args.model}_{dataset}_ckpt.jsonl"
        print(f"=== {dataset} ({args.model}, workers={args.workers}, timeout={args.timeout}) ===", flush=True)
        r = run_full_dataset(
            args.model, dataset, args.workers, args.timeout, args.max_retries, ckpt, args.resume,
            report_every=args.report_every, reasoning_effort=args.reasoning_effort,
            base_url=args.base_url, api_key=args.api_key,
        )
        results[dataset] = r
        print(json.dumps(r, ensure_ascii=False, indent=2), flush=True)

    out = OUTPUT_DIR / f"ticket_full_{args.model}_{stamp}.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nsaved: {out}")
    return 0


if __name__ == "__main__":
    main()