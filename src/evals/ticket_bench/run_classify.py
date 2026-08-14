"""Tobi classification benchmark (option A): supervised metrics on official GT.

Three classification tasks using the official Tobi-Bueck ground-truth fields:
- type_accuracy     : Incident / Request / Problem / Change (4 classes)
- priority_accuracy : low / medium / high (3 classes)
- queue_accuracy    : 10 department queues

Each sample is sent to the model as a classification question; the model must
answer with exactly one label. Metrics: accuracy per task + confusion matrix
per task + success rate.

Usage:
  python -m src.evals.ticket_bench.run_classify --model hy3 --workers 8 \
      --base-url http://127.0.0.1:8000/v1 --api-key "" --reasoning-effort no_think
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import queue
import threading
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from src.evals.ticket_bench.bench_core import BASE_URL

OUTPUT_DIR = Path("data/eval_results")
DATASET_DIR = Path("data/eval_datasets")
TOBI_PATH = DATASET_DIR / "tobi_tickets" / "dataset-tickets-multi-lang-4-20k.csv"

TASK_PROMPTS = {
    "type": "对以下客服工单进行分类，只能输出一个词：Incident、Request、Problem 或 Change。不要输出其他内容。",
    "priority": "对以下客服工单的紧急程度进行分类，只能输出一个词：low、medium 或 high。不要输出其他内容。",
    "queue": "对以下客服工单进行部门路由分类，只能输出以下队列名之一：Technical Support、Product Support、Customer Service、IT Support、Billing and Payments、Returns and Exchanges、Service Outages and Maintenance、Sales and Pre-Sales、Human Resources、General Inquiry。不要输出其他内容。",
    "itsm_label": "对以下 IT 服务工单进行分类，只能输出一个词：other、ticket 或 inquiry。不要输出其他内容。",
}

VALID = {
    "type": {"Incident", "Request", "Problem", "Change"},
    "priority": {"low", "medium", "high"},
    "queue": {"Technical Support", "Product Support", "Customer Service", "IT Support",
              "Billing and Payments", "Returns and Exchanges", "Service Outages and Maintenance",
              "Sales and Pre-Sales", "Human Resources", "General Inquiry"},
    "itsm_label": {"other", "ticket", "inquiry"},
}


def load_samples(task: str, limit: int = 0, dataset: str = "tobi") -> list[dict[str, Any]]:
    if dataset == "itsm":
        return load_itsm_samples(task, limit)
    df = pd.read_csv(TOBI_PATH)
    df = df.dropna(subset=["subject", "body", "type", "priority", "queue"])
    rows = []
    for _, row in df.iterrows():
        text = f"{row['subject']} {row['body']}".strip()[:600]
        if not text:
            continue
        label_map = {"type": str(row["type"]).strip(),
                     "priority": str(row["priority"]).strip().lower(),
                     "queue": str(row["queue"]).strip()}
        gt = label_map[task]
        if gt not in VALID[task]:
            continue
        rows.append({"text": text, "gt": gt})
    if limit and limit < len(rows):
        rows = rows[:limit]
    return rows


def load_itsm_samples(task: str, limit: int = 0) -> list[dict[str, Any]]:
    """ITSM train.jsonl: text + label(0=other,1=ticket,2=inquiry)."""
    import json as _json
    rows = []
    for line in Path("data/eval_datasets/itsm_tickets/train.jsonl").read_text(
            encoding="utf-8").strip().splitlines():
        try:
            obj = _json.loads(line)
        except Exception:  # noqa: BLE001
            continue
        text = str(obj.get("text", "")).strip()
        label = int(obj.get("label", -1))
        if not text or label < 0:
            continue
        gt = {0: "other", 1: "ticket", 2: "inquiry"}.get(label, "")
        if gt not in VALID["itsm_label"]:
            continue
        rows.append({"text": text[:600], "gt": gt})
    if limit and limit < len(rows):
        rows = rows[:limit]
    return rows


def call_classify(model: str, text: str, task: str, base_url: str, api_key: str,
                  reasoning_effort: str, timeout: float, retries: int = 3) -> dict[str, Any]:
    import time as _time
    import urllib.error
    import urllib.request
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": TASK_PROMPTS[task]},
            {"role": "user", "content": text},
        ],
        "reasoning_effort": reasoning_effort,
        "max_tokens": 30,
        "user": f"classify-{task}",
    }
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(f"{base_url}/chat/completions",
                                 data=json.dumps(payload).encode("utf-8"),
                                 headers=headers, method="POST")
    last_err = "retries exhausted"
    for attempt in range(retries + 1):
        t0 = _time.time()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                r = json.loads(resp.read().decode("utf-8"))
            content = str(r["choices"][0]["message"].get("content", "") or "").strip()
            dt = _time.time() - t0
            pred = ""
            for v in VALID[task]:
                if v.lower() in content.lower():
                    pred = v
                    break
            return {"ok": True, "latency": dt, "pred": pred, "error": None}
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 502, 503) and attempt < retries:
                _time.sleep(2 * (attempt + 1) + 1.5)
                last_err = f"HTTP {exc.code}"
                continue
            return {"ok": False, "latency": _time.time() - t0, "pred": "", "error": f"HTTP {exc.code}"}
        except Exception as exc:  # noqa: BLE001
            if attempt < retries and "timed out" in str(exc).lower():
                _time.sleep(2 * (attempt + 1))
                last_err = "timeout"
                continue
            return {"ok": False, "latency": _time.time() - t0, "pred": "", "error": str(exc)[:120]}
    return {"ok": False, "latency": 0.0, "pred": "", "error": last_err}


def run_task(model: str, task: str, workers: int, timeout: float, base_url: str,
             api_key: str, reasoning_effort: str, limit: int,
             checkpoint_path: Path, resume: bool, dataset: str = "tobi") -> dict[str, Any]:
    samples = load_samples(task, limit, dataset=dataset)
    total = len(samples)
    print(f"[{task}] loaded {total} samples", flush=True)

    done: dict[int, dict[str, Any]] = {}
    if resume and checkpoint_path.exists():
        for line in checkpoint_path.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
                done[r["idx"]] = r
            except Exception:  # noqa: BLE001
                continue
        print(f"[{task}] resumed {len(done)} completed", flush=True)

    pending: queue.Queue = queue.Queue()
    for idx, s in enumerate(samples):
        if idx not in done:
            pending.put((idx, s))

    stats_lock = threading.Lock()
    t0 = time.time()

    def worker():
        while True:
            try:
                idx, s = pending.get_nowait()
            except queue.Empty:
                return
            r = call_classify(model, s["text"], task, base_url, api_key, reasoning_effort, timeout,
                              retries=3)
            rec = {"idx": idx, "ok": r["ok"], "pred": r["pred"], "gt": s["gt"],
                   "latency": r["latency"], "error": r["error"]}
            with checkpoint_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            with stats_lock:
                done[idx] = rec
                n = len(done)
                if n % 100 == 0:
                    elapsed = time.time() - t0
                    rate = n / max(elapsed, 1)
                    eta = (total - n) / max(rate, 0.001) / 60
                    print(f"[{task}] {n}/{total} done, rate={rate:.1f}/s ETA={eta:.0f}m", flush=True)

    with cf.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(worker) for _ in range(workers)]
        for fut in cf.as_completed(futures):
            fut.result()
    wall = time.time() - t0

    ok_rows = [r for r in done.values() if r["ok"]]
    correct = sum(1 for r in ok_rows if r["pred"] == r["gt"])
    conf = Counter((r["gt"], r["pred"]) for r in ok_rows)
    return {
        "task": task,
        "model": model,
        "total": total,
        "ok_count": len(ok_rows),
        "success_rate": round(len(ok_rows) / max(total, 1), 4),
        "accuracy": round(correct / max(len(ok_rows), 1), 4),
        "correct": correct,
        "failed_count": total - len(ok_rows),
        "wall_seconds": round(wall, 2),
        "confusion": {f"{gt}->{pd}": c for (gt, pd), c in sorted(conf.items())},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Tobi/ITSM supervised classification benchmark.")
    parser.add_argument("--model", required=True)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--reasoning-effort", default="no_think")
    parser.add_argument("--base-url", default=BASE_URL)
    parser.add_argument("--api-key", default="")
    parser.add_argument("--limit", type=int, default=0, help="cap samples per task (0=all)")
    parser.add_argument("--dataset", default="tobi", choices=["tobi", "itsm"])
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    tasks = ("type", "priority", "queue") if args.dataset == "tobi" else ("itsm_label",)
    results = {}
    for task in tasks:
        ckpt = OUTPUT_DIR / f"ticket_classify_{args.model}_{args.dataset}_{task}_ckpt.jsonl"
        print(f"=== {task} ({args.model}, {args.dataset}) ===", flush=True)
        r = run_task(args.model, task, args.workers, args.timeout, args.base_url,
                     args.api_key, args.reasoning_effort, args.limit, ckpt, args.resume,
                     dataset=args.dataset)
        results[task] = r
        print(json.dumps(r, ensure_ascii=False, indent=2), flush=True)

    out = OUTPUT_DIR / f"ticket_classify_{args.model}_{args.dataset}_{stamp}.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nsaved: {out}")
    return 0


if __name__ == "__main__":
    main()
