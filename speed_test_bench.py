"""Speed test: deepseek-v4-flash vs hy3/glm-5.2 with reduced reasoning effort.

Runs N samples with W workers through the same bench pipeline and reports
throughput + latency so we can decide the final benchmark config.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[0]))

from src.evals.ticket_bench.bench_core import load_tobi, single_call


def main() -> int:
    parser = argparse.ArgumentParser(description="Speed test for bench models.")
    parser.add_argument("--model", required=True)
    parser.add_argument("--workers", type=int, default=18)
    parser.add_argument("--samples", type=int, default=60)
    parser.add_argument("--reasoning-effort", default="no_think")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000/v1")
    parser.add_argument("--api-key", default="")
    args = parser.parse_args()

    samples = load_tobi(0)[: args.samples]
    t0 = time.time()
    ok = 0
    failed = 0
    lat = []

    def work(s):
        return single_call(args.model, s, retries=0, timeout=args.timeout,
                           reasoning_effort=args.reasoning_effort,
                           base_url=args.base_url, api_key=args.api_key)

    with cf.ThreadPoolExecutor(max_workers=args.workers) as pool:
        for r in pool.map(work, samples):
            if r["ok"]:
                ok += 1
                lat.append(r["latency"])
            else:
                failed += 1
                print(f"FAIL: {r.get('error', '')[:120]}", flush=True)

    wall = time.time() - t0
    lat_sorted = sorted(lat)
    def pct(p):
        return round(lat_sorted[min(len(lat_sorted) - 1, int(p * len(lat_sorted)))], 2) if lat_sorted else 0
    print(f"\n[{args.model} effort={args.reasoning_effort}] workers={args.workers} samples={args.samples}")
    print(f"  ok={ok} failed={failed} wall={wall:.1f}s")
    print(f"  throughput={ok / wall:.3f} rps  (full tobi 18537 -> {18537 / max(ok / wall, 1e-9) / 3600:.1f}h)")
    print(f"  latency p50={pct(0.50)} p95={pct(0.95)} p99={pct(0.99)} max={max(lat_sorted) if lat_sorted else 0:.1f}")
    return 0


if __name__ == "__main__":
    main()
