"""Benchmark monitor: watch progress + live metrics for all running runs.

Usage:
  python monitor_bench.py              # single snapshot
  python monitor_bench.py --watch 60   # loop every 60s until Ctrl+C
"""
from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

PROJECT = Path("/data/workspace/Knowledge-Ops-Agent-for-Ticket-Triage")
OUTPUT_DIR = PROJECT / "data/eval_results"

MODELS = {
    "hy3": {"tobi": 18537, "itsm": 900, "baseline": 17171, "log": "/tmp/bench_hy3.log"},
    "deepseek-v4-flash-202605": {"tobi": 18537, "itsm": 900, "baseline": 5, "log": "/tmp/bench_flash202605.log"},
}
REF_RPS = {"hy3": 0.3, "deepseek-v4-flash-202605": 0.5}


def get_processes() -> list[dict]:
    out = subprocess.run(["ps", "aux"], capture_output=True, text=True).stdout
    procs = []
    for line in out.splitlines():
        if "src.evals.ticket_bench.run_full" in line and "grep" not in line:
            parts = line.split(None, 10)
            model = ""
            if "--model" in line:
                model = line.split("--model")[1].split()[0]
            procs.append({"pid": parts[1], "cpu": parts[2], "mem": parts[3], "model": model})
    return procs


def parse_ckpt(model: str) -> dict:
    ckpt = OUTPUT_DIR / f"ticket_full_{model}_tobi_ckpt.jsonl"
    if not ckpt.exists():
        return {"exists": False}
    rows = [json.loads(l) for l in ckpt.read_text(encoding="utf-8").splitlines() if l.strip()]
    ok_rows = [r for r in rows if r.get("ok")]
    fail_rows = [r for r in rows if not r.get("ok")]
    total = len(rows)
    n_ok = len(ok_rows)
    n_fail = len(fail_rows)
    target = MODELS[model]["tobi"]
    baseline = MODELS[model]["baseline"]

    lats = sorted(r["latency"] for r in ok_rows)
    def pct(p):
        return round(lats[min(len(lats) - 1, int(p * len(lats)))], 1) if lats else 0.0

    tools = Counter()
    for r in ok_rows:
        for t in (r.get("tool_calls") or []):
            tools[t] += 1

    delta = sum(max(r.get("prompt_tokens", 0) - baseline, 0) for r in ok_rows)
    comp = sum(r.get("completion_tokens", 0) for r in ok_rows)
    errs = Counter(str(r.get("error", ""))[:30] for r in fail_rows)

    return {
        "exists": True,
        "total": total,
        "target": target,
        "pct": total / target * 100,
        "n_ok": n_ok,
        "n_fail": n_fail,
        "success_rate": n_ok / max(total, 1),
        "lat_p50": pct(0.50), "lat_p95": pct(0.95), "lat_p99": pct(0.99),
        "tools": dict(tools.most_common()),
        "no_tool": sum(1 for r in ok_rows if not r.get("tool_calls")),
        "delta_tokens": delta + comp,
        "delta_per_req": round((delta + comp) / max(n_ok, 1), 1),
        "errors": dict(errs.most_common(3)),
    }


def read_log_tail(log: str, n: int = 3) -> str:
    try:
        lines = Path(log).read_text(encoding="utf-8", errors="replace").splitlines()
        return "\n".join(lines[-n:])
    except FileNotFoundError:
        return "(no log)"


class CkptTracker:
    """Incremental checkpoint reader: only parses NEW lines each poll() call,
    so per-second refresh stays cheap even with 19k+ rows."""

    def __init__(self, model: str):
        self.model = model
        self.path = OUTPUT_DIR / f"ticket_full_{model}_tobi_ckpt.jsonl"
        self.offset = 0
        self.total = 0
        self.n_ok = 0
        self.n_fail = 0
        self.lats: list[float] = []
        self.tools: Counter = Counter()
        self.no_tool = 0
        self.prompt_sum = 0
        self.comp_sum = 0
        self.errors: Counter = Counter()

    def poll(self) -> None:
        if not self.path.exists():
            return
        with open(self.path, "r", encoding="utf-8") as fh:
            fh.seek(self.offset)
            lines = fh.readlines()
            self.offset = fh.tell()
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            self.total += 1
            if r.get("ok"):
                self.n_ok += 1
                self.lats.append(float(r.get("latency", 0)))
                tcs = r.get("tool_calls") or []
                for t in tcs:
                    self.tools[t] += 1
                if not tcs:
                    self.no_tool += 1
                self.prompt_sum += int(r.get("prompt_tokens", 0))
                self.comp_sum += int(r.get("completion_tokens", 0))
            else:
                self.n_fail += 1
                self.errors[str(r.get("error", ""))[:30]] += 1

    def info(self) -> dict:
        target = MODELS[self.model]["tobi"]
        baseline = MODELS[self.model]["baseline"]
        lats = sorted(self.lats)
        def pct(p):
            return round(lats[min(len(lats) - 1, int(p * len(lats)))], 1) if lats else 0.0
        delta_prompt = max(self.prompt_sum - self.n_ok * baseline, 0) if baseline > 0 else self.prompt_sum
        return {
            "exists": True,
            "total": self.total,
            "target": target,
            "pct": self.total / target * 100,
            "n_ok": self.n_ok,
            "n_fail": self.n_fail,
            "success_rate": self.n_ok / max(self.total, 1),
            "lat_p50": pct(0.50), "lat_p95": pct(0.95), "lat_p99": pct(0.99),
            "tools": dict(self.tools.most_common()),
            "no_tool": self.no_tool,
            "delta_tokens": delta_prompt + self.comp_sum,
            "delta_per_req": round((delta_prompt + self.comp_sum) / max(self.n_ok, 1), 1),
            "errors": dict(self.errors.most_common(3)),
        }


def snapshot() -> dict:
    rows = {}
    procs = get_processes()
    running_models = {p["model"] for p in procs}
    for model, cfg in MODELS.items():
        info = parse_ckpt(model)
        info["running"] = model in running_models
        info["log_tail"] = read_log_tail(cfg["log"])
        rows[model] = info
    rows["_procs"] = procs
    return rows


def render(s: dict) -> str:
    now = datetime.now().strftime("%m-%d %H:%M:%S")
    lines = [f"===== 测评监控 {now} ====="]
    for model, info in s.items():
        if model.startswith("_"):
            continue
        lines.append(f"\n--- {model} {'[运行中]' if info.get('running') else '[未运行]'} ---")
        if not info.get("exists"):
            lines.append("  尚无 checkpoint")
            continue
        lines.append(f"  进度: {info['total']}/{info['target']} ({info['pct']:.1f}%)")
        bar_w = 40
        filled = int(bar_w * info['pct'] / 100)
        lines.append(f"  [{('#' * filled).ljust(bar_w)}]")
        lines.append(f"  成功: {info['n_ok']} | 失败: {info['n_fail']} | success_rate: {info['success_rate']*100:.1f}%")
        if info["errors"]:
            err_str = " | ".join(f"{k}={v}" for k, v in info["errors"].items())
            lines.append(f"  失败原因: {err_str}")
        lines.append(f"  延迟: p50={info['lat_p50']}s p95={info['lat_p95']}s p99={info['lat_p99']}s")
        tools_str = " | ".join(f"{k}={v} ({v/info['n_ok']*100:.0f}%)" for k, v in list(info["tools"].items())[:3])
        lines.append(f"  工具: {tools_str} | 无工具={info['no_tool']}")
        lines.append(f"  delta tokens/请求: {info['delta_per_req']}")
        lines.append(f"  日志尾: {info['log_tail'].replace(chr(10), ' | ')}")
    lines.append("\n进程:")
    for p in s.get("_procs", []):
        lines.append(f"  PID {p['pid']} CPU {p['cpu']}% MEM {p['mem']}% model={p['model']}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Monitor benchmark progress.")
    parser.add_argument("--watch", type=int, default=0, help="loop interval seconds (0 = single snapshot)")
    parser.add_argument("--json", action="store_true", help="output raw JSON")
    parser.add_argument("--no-ansi", action="store_true",
                        help="force append mode even in terminals (use if screen not refreshing)")
    parser.add_argument("--ansi", action="store_true",
                        help="force in-place refresh mode (cursor-up redraw, no clear-screen)")
    args = parser.parse_args()

    if args.json:
        print(json.dumps(snapshot(), ensure_ascii=False, indent=2))
        return 0

    if args.watch > 0:
        import os
        is_tty = sys.stdout.isatty()
        term = os.environ.get("TERM", "")
        # 默认: TTY 且 TERM 非 dumb 时用原地刷新(回退覆盖); 可 --ansi 强制 / --no-ansi 关闭
        use_ansi = args.ansi or ((not args.no_ansi) and is_tty and term not in ("", "dumb", "unknown"))
        trackers = {m: CkptTracker(m) for m in MODELS}
        mode = "原地刷新(回退覆盖)" if use_ansi else "追加模式(带时间戳)"
        print(f"[monitor] 刷新间隔 {args.watch}s | 模式: {mode} | Ctrl+C 退出\n", flush=True)
        last_lines = 0
        try:
            while True:
                # 增量读取新行
                for t in trackers.values():
                    t.poll()
                rows: dict = {}
                procs = get_processes()
                running_models = {p["model"] for p in procs}
                for model, t in trackers.items():
                    info = t.info()
                    info["running"] = model in running_models
                    info["log_tail"] = read_log_tail(MODELS[model]["log"])
                    rows[model] = info
                rows["_procs"] = procs
                text = render(rows)
                if use_ansi:
                    # 原地刷新：先上移上次快照行数并清空，再重绘（不清屏、不闪烁）
                    if last_lines:
                        sys.stdout.write(f"\033[{last_lines}A\033[J")
                    sys.stdout.write(text + "\n")
                    sys.stdout.flush()
                    last_lines = text.count("\n") + 1
                else:
                    # 追加模式：完整快照 + 时间戳分隔线，逐次追加
                    print(text)
                    print("-" * 60, flush=True)
                time.sleep(args.watch)
        except KeyboardInterrupt:
            print("\n[monitor] 已停止")
        return 0

    print(render(snapshot()))
    return 0


if __name__ == "__main__":
    main()
