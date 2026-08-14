"""Pre-benchmark sanity check: data loading, baseline probe, single call, metrics."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[0]))

from src.evals.ticket_bench.bench_core import (
    get_baseline_prompt_tokens,
    load_itsm,
    load_tobi,
    single_call,
)

print("=== 1. 数据加载验证 ===")
tobi = load_tobi(0)
itsm = load_itsm(0)
print(f"Tobi 有效样本: {len(tobi)} (指南预期 ~18537)")
print(f"ITSM 有效样本: {len(itsm)} (指南预期 ~900)")
assert len(tobi) > 15000, "Tobi 样本数异常"
assert 800 <= len(itsm) <= 950, "ITSM 样本数异常"
print("Tobi 样例:", json.dumps(tobi[0], ensure_ascii=False)[:200])
print("ITSM 样例:", json.dumps(itsm[0], ensure_ascii=False)[:200])
print("数据加载 OK")

print("\n=== 2. baseline prompt tokens 测量 ===")
for m in ("hy3", "glm-5.2"):
    base = get_baseline_prompt_tokens(m)
    print(f"{m}: baseline_prompt_tokens={base} (指南预期 ~17000)")
    assert base > 10000, f"{m} baseline 异常: {base}"
print("baseline 测量 OK")

print("\n=== 3. 单次调用验证（含工具调用模式） ===")
for m in ("hy3", "glm-5.2"):
    r = single_call(m, {"text": "VPN 登录失败提示 token 过期，请帮我查一下知识库", "expected": "kb", "type": "smoke"}, retries=1, timeout=60)
    print(f"{m}: ok={r['ok']} latency={r['latency']:.1f}s tool_calls={r['tool_calls']} "
          f"prompt={r['prompt_tokens']} completion={r['completion_tokens']} err={r['error']}")
    assert r["ok"], f"{m} 调用失败: {r['error']}"
print("单次调用 OK")

print("\n=== 4. 指标计算验证（基于已有结果模拟） ===")
ok_rows = [
    {"ok": True, "latency": 1.0, "tool_calls": ["search_kb"], "content_len": 50,
     "prompt_tokens": 20000, "completion_tokens": 200, "type": "Incident", "expected": "kb"},
    {"ok": True, "latency": 2.0, "tool_calls": ["get_ticket_status"], "content_len": 30,
     "prompt_tokens": 20000, "completion_tokens": 300, "type": "itsm/1", "expected": "ticket"},
    {"ok": True, "latency": 3.0, "tool_calls": ["create_escalation_draft"], "content_len": 0,
     "prompt_tokens": 20000, "completion_tokens": 100, "type": "itsm/0", "expected": "kb"},
]
lat = sorted(r["latency"] for r in ok_rows)
def pct(p):
    return lat[min(len(lat) - 1, int(p * len(lat)))]
def route_of(r):
    return "ticket" if any("ticket" in t for t in r["tool_calls"]) else "kb"
correct = sum(1 for r in ok_rows if route_of(r) == r.get("expected", "kb"))
base = 18000
delta_prompt = sum(max(r["prompt_tokens"] - base, 0) for r in ok_rows)
total_comp = sum(r["completion_tokens"] for r in ok_rows)
kb_calls = sum(1 for r in ok_rows if any("search_kb" in t for t in r["tool_calls"]))
esc_calls = sum(1 for r in ok_rows if any("escalation" in t for t in r["tool_calls"]))
print(f"route_accuracy(ITSM口径): {round(correct/max(len(ok_rows),1),4)} (期望 1.0)")
print(f"kb_grounding_rate(Tobi口径): {round(kb_calls/max(len(ok_rows),1),4)} (期望 0.3333)")
print(f"escalation_signal_rate: {round(esc_calls/max(len(ok_rows),1),4)} (期望 0.3333)")
print(f"answerable_rate: {round(sum(1 for r in ok_rows if r['content_len']>0 or r['tool_calls'])/max(len(ok_rows),1),4)} (期望 1.0)")
print(f"latency_p50={pct(0.50)} p95={pct(0.95)} p99={pct(0.99)} max={max(lat)} (期望 2/3/3/3)")
print(f"delta_total_tokens={delta_prompt+total_comp} (期望 6600)")
print("指标计算 OK")

print("\n=== 全部前置验证通过，可以开始全量测评 ===")
