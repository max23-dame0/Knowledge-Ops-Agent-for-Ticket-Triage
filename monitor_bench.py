"""Benchmark monitor: watch progress + live metrics for ALL running evals.

Auto-discovers running benchmark processes (run_full / run_classify) and their
checkpoint files, so new tasks need no manual config.

Usage:
  python monitor_bench.py                    # single snapshot
  python monitor_bench.py --watch 1          # 1s refresh (in-place on TTY)
  python monitor_bench.py --watch 1 --ansi   # force in-place refresh
  python monitor_bench.py --watch 1 --no-ansi# force append mode
  python monitor_bench.py --json             # raw JSON
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

PROJECT = Path("/data/workspace/Knowledge-Ops-Agent-for-Ticket-Triage")
OUTPUT_DIR = PROJECT / "data/eval_results"

TARGETS = {"tobi": 18537, "itsm": 900}
CLASSIFY_TARGETS = {"type": 2000, "priority": 2000, "queue": 2000, "itsm_label": 900}


def get_processes() -> list[dict]:
    out = subprocess.run(["ps", "aux"], capture_output=True, text=True).stdout
    procs = []
    for line in out.splitlines():
        if "src.evals.ticket_bench.run" in line and "grep" not in line and "monitor" not in line:
            parts = line.split(None, 10)
            kind = "full" if "run_full" in line else ("classify" if "run_classify" in line else "?")
            model = ""
            if "--model" in line:
                model = line.split("--model")[1].split()[0]
            procs.append({"pid": parts[1], "cpu": parts[2], "mem": parts[3],
                          "model": model, "kind": kind})
    return procs


def _parse_ckpt_file(path: Path, target: int | None, baseline: int = 0) -> dict:
    rows = []
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except FileNotFoundError:
        return {"exists": False}
    ok_rows = [r for r in rows if r.get("ok")]
    fail_rows = [r for r in rows if not r.get("ok")]
    total = len(rows)
    n_ok = len(ok_rows)
    n_fail = len(fail_rows)

    lats = sorted(r["latency"] for r in ok_rows)
    def pct(p):
        return round(lats[min(len(lats) - 1, int(p * len(lats)))], 1) if lats else 0.0

    tools = Counter()
    for r in ok_rows:
        for t in (r.get("tool_calls") or []):
            tools[t] += 1

    prompt_sum = sum(r.get("prompt_tokens", 0) for r in ok_rows)
    comp_sum = sum(r.get("completion_tokens", 0) for r in ok_rows)
    delta_prompt = max(prompt_sum - n_ok * baseline, 0) if baseline > 0 else prompt_sum
    errs = Counter(str(r.get("error", ""))[:28] for r in fail_rows)

    return {
        "exists": True,
        "path": path.name,
        "total": total,
        "target": target or total,
        "n_ok": n_ok,
        "n_fail": n_fail,
        "success_rate": n_ok / max(total, 1),
        "lat_p50": pct(0.50), "lat_p95": pct(0.95), "lat_p99": pct(0.99),
        "tools": dict(tools.most_common()),
        "no_tool": sum(1 for r in ok_rows if not r.get("tool_calls")),
        "delta_per_req": round((delta_prompt + comp_sum) / max(n_ok, 1), 1),
        "errors": dict(errs.most_common(2)),
    }


def discover_checkpoints() -> list[dict]:
    items = []
    if not OUTPUT_DIR.exists():
        return items
    # full: ticket_full_{model}_{dataset}_ckpt.jsonl（dataset ∈ {tobi, itsm}）
    for path in sorted(OUTPUT_DIR.glob("ticket_full_*_ckpt.jsonl")):
        name = path.name[len("ticket_full_"):-len("_ckpt.jsonl")]
        if name.endswith("_tobi") or name.endswith("_itsm"):
            model, dataset = name.rsplit("_", 1)
        else:
            model, dataset = name, "?"
        baseline = 0 if "deepseek" in model or "gemini" in model else 17171
        info = _parse_ckpt_file(path, TARGETS.get(dataset), baseline)
        if info["exists"]:
            info.update({"kind": "full", "model": model, "dataset": dataset})
            items.append(info)
    # classify: ticket_classify_{model}_{dataset}_{task}_ckpt.jsonl（dataset ∈ {tobi, itsm}）
    for path in sorted(OUTPUT_DIR.glob("ticket_classify_*_ckpt.jsonl")):
        name = path.name[len("ticket_classify_"):-len("_ckpt.jsonl")]
        if "_tobi_" in name:
            head, task = name.rsplit("_tobi_", 1)
            model, dataset = head, "tobi"
        elif "_itsm_" in name:
            head, task = name.rsplit("_itsm_", 1)
            model, dataset = head, "itsm"
        else:
            continue
        info = _parse_ckpt_file(path, CLASSIFY_TARGETS.get(task))
        if info["exists"]:
            info.update({"kind": "classify", "model": model, "dataset": dataset, "task": task})
            items.append(info)
    return items


def render(items: list[dict], procs: list[dict]) -> str:
    now = datetime.now().strftime("%m-%d %H:%M:%S")
    lines = [f"===== 测评监控 {now} ====="]

    by_model: dict[str, list[dict]] = {}
    for it in items:
        by_model.setdefault(it["model"], []).append(it)
    if not by_model:
        lines.append("(暂无 checkpoint)")

    running_models = {p["model"] for p in procs}
    for model in sorted(by_model):
        lines.append(f"\n--- {model} {'[运行中]' if model in running_models else '[未运行]'} ---")
        for it in sorted(by_model[model], key=lambda x: (x["kind"], x.get("task", x.get("dataset")))):
            tag = f"{it['kind']}/{it.get('task', it.get('dataset'))}"
            lines.append(f"  [{tag}] {it['total']}/{it['target']} ({it['total']/max(it['target'],1)*100:.1f}%)")
            lines.append(f"    ok={it['n_ok']} fail={it['n_fail']} success={it['success_rate']*100:.1f}%"
                         f" | latency p50={it['lat_p50']}s p95={it['lat_p95']}s"
                         f" | delta_tok/req={it['delta_per_req']}")
            if it["tools"]:
                tstr = " | ".join(f"{k}={v}" for k, v in list(it["tools"].items())[:3])
                lines.append(f"    tools: {tstr}")
            if it["errors"]:
                estr = " | ".join(f"{k}:{v}" for k, v in it["errors"].items())
                lines.append(f"    errors: {estr}")

    lines.append("\n进程:")
    if not procs:
        lines.append("  (无运行中评测进程)")
    for p in procs:
        lines.append(f"  PID {p['pid']} CPU {p['cpu']}% MEM {p['mem']}% {p['kind']} model={p['model']}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Monitor benchmark progress (auto-discover).")
    parser.add_argument("--watch", type=int, default=0, help="refresh interval seconds (0 = single snapshot)")
    parser.add_argument("--json", action="store_true", help="output raw JSON")
    parser.add_argument("--no-ansi", action="store_true", help="force append mode")
    parser.add_argument("--ansi", action="store_true", help="force in-place refresh")
    args = parser.parse_args()

    if args.json:
        print(json.dumps({"processes": get_processes(), "checkpoints": discover_checkpoints()},
                         ensure_ascii=False, indent=2))
        return 0

    if args.watch > 0:
        import os
        term = os.environ.get("TERM", "")
        # 不依赖 isatty（IDE 终端常为 False）；TERM 正常即原地刷新，dumb/空才追加
        use_ansi = (not args.no_ansi) and term not in ("", "dumb", "unknown")
        mode = "原地刷新(回退覆盖)" if use_ansi else "追加模式(带时间戳)"
        print(f"[monitor] 刷新间隔 {args.watch}s | 模式: {mode} | Ctrl+C 退出\n", flush=True)
        last_lines = 0
        try:
            while True:
                items = discover_checkpoints()
                procs = get_processes()
                text = render(items, procs)
                if use_ansi:
                    if last_lines:
                        sys.stdout.write(f"\033[{last_lines}A\033[J")
                    sys.stdout.write(text + "\n")
                    sys.stdout.flush()
                    last_lines = text.count("\n") + 1
                else:
                    print(text)
                    print("-" * 60, flush=True)
                time.sleep(args.watch)
        except KeyboardInterrupt:
            print("\n[monitor] 已停止")
        return 0

    print(render(discover_checkpoints(), get_processes()))
    return 0


if __name__ == "__main__":
    main()
