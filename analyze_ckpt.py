"""Analyze in-progress checkpoint stats for a model's tobi run."""
from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter
from pathlib import Path

OUTPUT_DIR = Path("data/eval_results")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    args = parser.parse_args()

    ckpt = OUTPUT_DIR / f"ticket_full_{args.model}_tobi_ckpt.jsonl"
    rows = [json.loads(l) for l in ckpt.read_text(encoding="utf-8").splitlines() if l.strip()]
    ok_rows = [r for r in rows if r.get("ok")]
    fail_rows = [r for r in rows if not r.get("ok")]

    total = len(rows)
    n_ok = len(ok_rows)
    n_fail = len(fail_rows)
    print(f"=== {args.model} tobi 中间统计 ===")
    print(f"已处理: {total} / 18537 ({total/18537*100:.1f}%)")
    print(f"成功: {n_ok} | 失败: {n_fail} | success_rate: {n_ok/max(total,1):.4f}")

    # 失败原因分布
    if fail_rows:
        errs = Counter(str(r.get("error", ""))[:40] for r in fail_rows)
        print("\n失败原因分布:")
        for err, cnt in errs.most_common(5):
            print(f"  {err}: {cnt}")

    if not ok_rows:
        print("\n(暂无成功数据)")
        return

    lats = sorted(r["latency"] for r in ok_rows)
    def pct(p):
        return round(lats[min(len(lats) - 1, int(p * len(lats)))], 2)
    print(f"\n延迟(s): p50={pct(0.50)} p95={pct(0.95)} p99={pct(0.99)} max={round(max(lats),1)} avg={round(statistics.mean(lats),2)}")

    # 工具调用分布
    tools = Counter()
    for r in ok_rows:
        for t in (r.get("tool_calls") or []):
            tools[t] += 1
    print(f"\n工具调用分布 (共 {sum(tools.values())} 次):")
    for t, cnt in tools.most_common():
        print(f"  {t}: {cnt} ({cnt/n_ok*100:.1f}%)")

    no_tool = sum(1 for r in ok_rows if not r.get("tool_calls"))
    print(f"无工具调用直接回答: {no_tool} ({no_tool/n_ok*100:.1f}%)")

    # token
    prompt_t = sum(r.get("prompt_tokens", 0) for r in ok_rows)
    comp_t = sum(r.get("completion_tokens", 0) for r in ok_rows)
    baseline = 17171  # hy3 knot 基线
    delta = sum(max(r.get("prompt_tokens", 0) - baseline, 0) for r in ok_rows)
    print(f"\ntoken: prompt_total={prompt_t} comp_total={comp_t} delta_prompt={delta} delta_total={delta+comp_t}")
    print(f"平均每请求 delta tokens: {(delta+comp_t)/n_ok:.1f}")

    # content_len（新行才有，旧行缺字段）
    has_cl = [r for r in ok_rows if "content_len" in r]
    if has_cl:
        avg_cl = statistics.mean(r["content_len"] for r in has_cl)
        empty = sum(1 for r in has_cl if r["content_len"] <= 0 and not r.get("tool_calls"))
        print(f"\n回答质量: 平均 content_len={avg_cl:.1f} (样本{len(has_cl)}) | 空回答无工具: {empty} ({empty/len(has_cl)*100:.1f}%)")


if __name__ == "__main__":
    main()
