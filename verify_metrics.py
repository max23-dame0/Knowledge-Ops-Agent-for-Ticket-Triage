"""Independent metric verification: recompute metrics from checkpoints with a
separate implementation and compare against run_full.py logic.

This script implements the metric formulas from scratch (not importing from
run_full.py) so bugs in one implementation don't hide in the other.
"""
from __future__ import annotations

import collections
import json
from collections import Counter
from pathlib import Path

OUTPUT_DIR = Path("data/eval_results")
TARGET_TOTAL = 18537  # tobi 有效样本
TARGET_ITSM = 900


def load_rows(ckpt: Path) -> list[dict]:
    rows = [json.loads(l) for l in ckpt.read_text(encoding="utf-8").splitlines() if l.strip()]
    return rows


def verify_tobi(ckpt: Path, baseline: int, label: str) -> None:
    rows = load_rows(ckpt)
    ok_rows = [r for r in rows if r.get("ok")]
    n_ok = len(ok_rows)
    n_fail = len(rows) - n_ok

    print(f"\n========== {label} (Tobi) ==========")
    print(f"checkpoint 行数: {len(rows)} | 成功: {n_ok} | 失败: {n_fail}")

    # 1. success_rate: ok / total
    success_rate = n_ok / TARGET_TOTAL
    print(f"[1] success_rate = {n_ok}/{TARGET_TOTAL} = {success_rate:.4f}")

    # 2. latency 分位 (独立实现)
    lats = sorted(r["latency"] for r in ok_rows)
    def pct(p):
        if not lats:
            return 0.0
        return round(lats[min(len(lats) - 1, int(p * len(lats)))], 2)
    print(f"[2] latency p50={pct(0.50)} p95={pct(0.95)} p99={pct(0.99)} max={round(max(lats),2) if lats else 0}")

    # 3. Tobi 质量指标 (独立实现)
    kb = sum(1 for r in ok_rows if any("search_kb" in t for t in (r.get("tool_calls") or [])))
    esc = sum(1 for r in ok_rows if any("escalation" in t for t in (r.get("tool_calls") or [])))
    tkt = sum(1 for r in ok_rows if any("ticket" in t for t in (r.get("tool_calls") or [])))
    ans = sum(1 for r in ok_rows if (r.get("content_len", 0) or 0) > 0 or r.get("tool_calls"))
    print(f"[3] kb_grounding_rate = {kb}/{n_ok} = {kb/n_ok:.4f}")
    print(f"    escalation_signal_rate = {esc}/{n_ok} = {esc/n_ok:.4f}")
    print(f"    (ticket 工具命中: {tkt})")
    print(f"    answerable_rate = {ans}/{n_ok} = {ans/n_ok:.4f}")

    # 4. token (独立实现)
    tp = sum(r.get("prompt_tokens", 0) for r in ok_rows)
    tc = sum(r.get("completion_tokens", 0) for r in ok_rows)
    dp = sum(max(r.get("prompt_tokens", 0) - baseline, 0) for r in ok_rows)
    print(f"[4] total_prompt={tp} total_comp={tc} delta_prompt={dp} delta_total={dp+tc}")
    print(f"    avg_delta_per_req={(dp+tc)/n_ok:.1f}")

    # 5. 数据完整性检查
    missing_cl = sum(1 for r in ok_rows if "content_len" not in r)
    dup = n_ok - len({tuple(r.get("sample_id", ())) for r in ok_rows})
    print(f"[5] 缺 content_len 的行: {missing_cl} | 重复 sample_id: {dup}")
    if missing_cl:
        print("    ⚠️ 旧 checkpoint 行缺 content_len，answerable_rate 会低估（兜底 0）")


def verify_itsm(ckpt: Path, label: str) -> None:
    rows = load_rows(ckpt)
    ok_rows = [r for r in rows if r.get("ok")]
    n_ok = len(ok_rows)
    print(f"\n========== {label} (ITSM) ==========")
    print(f"checkpoint 行数: {len(rows)} | 成功: {n_ok}")

    # route_accuracy: label 1 -> ticket 工具, 0/2 -> kb
    def route_of(r):
        return "ticket" if any("ticket" in t for t in (r.get("tool_calls") or [])) else "kb"
    correct = sum(1 for r in ok_rows if route_of(r) == r.get("expected", "kb"))
    print(f"[1] route_accuracy = {correct}/{n_ok} = {correct/n_ok:.4f}")

    # label 分布
    lbl = Counter(r.get("label", -1) for r in ok_rows)
    print(f"[2] label 分布: {dict(lbl)}")

    # 混淆矩阵
    conf = collections.Counter((r.get("label", -1), route_of(r)) for r in ok_rows)
    print(f"[3] 混淆 (label -> route): {dict(conf)}")


def main() -> None:
    # 当前运行中的两个模型（tobi）
    verify_tobi(OUTPUT_DIR / "ticket_full_hy3_tobi_ckpt.jsonl", baseline=17171, label="hy3")
    verify_tobi(OUTPUT_DIR / "ticket_full_deepseek-v4-flash-202605_tobi_ckpt.jsonl", baseline=5, label="flash-202605")

    # ITSM 若已有数据
    itsm_hy3 = OUTPUT_DIR / "ticket_full_hy3_itsm_ckpt.jsonl"
    if itsm_hy3.exists() and itsm_hy3.stat().st_size > 0:
        verify_itsm(itsm_hy3, "hy3")


if __name__ == "__main__":
    main()
