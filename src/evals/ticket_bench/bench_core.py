"""Enterprise ticket dataset evaluation - Tobi-Bueck 20k + ITSM 900.

Two evaluation modes:

1. ITSM (has ground-truth label 0/1/2 = other / ticket / inquiry):
   - route_accuracy: predicted route (ticket vs kb) vs label

2. Tobi (real ITIL tickets: Incident/Request/Problem/Change, open-domain):
   - No project-internal route ground truth. We measure *handling quality*:
     - kb_grounding_rate: model calls search_kb (appropriate for open tickets)
     - escalation_signal_rate: how often it proposes escalation
     - answerable_rate: produces a non-empty response

Shared quantitative metrics for both:
- success_rate, timeout/retry counts, latency (p50/p95/p99/max), throughput
- token consumption: raw + delta (baseline overhead subtracted)
- error breakdown

Designed for a cloud host (32 cores / 64GB): --workers controls concurrency.
Each in-flight request spawns one knot-cli subprocess through the proxy, so
workers <= (RAM_GB - 8) / 1.5 is a sane guideline.
"""

from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path
from typing import Any

import pandas as pd

BASE_URL = "http://127.0.0.1:8000/v1"
DATASET_DIR = Path("data/eval_datasets")
TOBI_PATH = DATASET_DIR / "tobi_tickets" / "dataset-tickets-multi-lang-4-20k.csv"
ITSM_PATH = DATASET_DIR / "itsm_tickets" / "train.jsonl"

_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_ticket_status",
            "description": "按 ticket_id 查询工单状态",
            "parameters": {"type": "object", "properties": {"ticket_id": {"type": "string"}}, "required": ["ticket_id"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_kb",
            "description": "Search the local knowledge base for grounded support evidence.",
            "parameters": {"type": "object", "properties": {"query": {"type": "string"}, "top_k": {"type": "integer"}}, "required": ["query"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_escalation_draft",
            "description": "Generate a structured escalation suggestion.",
            "parameters": {"type": "object", "properties": {"issue_summary": {"type": "string"}, "evidence": {"type": "array", "items": {"type": "string"}}}, "required": ["issue_summary"]},
        },
    },
]

# Knot-cli reports ~17k constant prompt tokens per request (Hermes agent
# resident context: system prompt + skills + tool definitions). This is an
# architectural overhead of the agent runtime, not per-request business cost.
# We measure the baseline once per model and report DELTA tokens (business
# cost) alongside raw totals so models compare fairly.
_BASELINE_CACHE: dict[str, int] = {}


def get_baseline_prompt_tokens(model: str, base_url: str = BASE_URL) -> int:
    """Return the measured baseline prompt overhead for the model (cached)."""
    if model in _BASELINE_CACHE:
        return _BASELINE_CACHE[model]
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "hi"}],
        "reasoning_effort": "high",
        "max_context_tokens": "1M",
        "user": "baseline-probe",
    }
    req = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            r = json.loads(resp.read().decode("utf-8"))
        base = r.get("usage", {}).get("prompt_tokens", 0)
    except Exception:  # noqa: BLE001
        base = 0
    _BASELINE_CACHE[model] = base
    return base


def load_tobi(sample: int = 0, seed: int = 42) -> list[dict[str, Any]]:
    """Load Tobi tickets. sample=0 means ALL valid rows (full 20k pool)."""
    import random

    df = pd.read_csv(TOBI_PATH)
    df = df.dropna(subset=["subject", "body"])
    rows = []
    for _, row in df.iterrows():
        text = f"{row['subject']} {row['body']}".strip()
        ttype = str(row.get("type", "")).strip()
        if not text:
            continue
        rows.append({
            "text": text[:600],
            "expected": "incident" if ttype == "Incident" else "ticket",
            "type": ttype,
            "language": str(row.get("language", "")),
        })
    if sample and sample < len(rows):
        rng = random.Random(seed)
        rows = rng.sample(rows, sample)
    return rows


def load_itsm(sample: int = 0, seed: int = 42) -> list[dict[str, Any]]:
    """Load ITSM tickets. sample=0 means all 900."""
    import random

    lines = ITSM_PATH.read_text(encoding="utf-8").strip().splitlines()
    rows = []
    for line in lines:
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue  # skip malformed lines; corrupt rows are not worth failing the run
        text = str(obj.get("text", "")).strip()
        label = int(obj.get("label", -1))
        if not text or label < 0:
            continue
        expected = "ticket" if label == 1 else "kb"
        rows.append({"text": text[:600], "expected": expected, "type": f"itsm/{label}", "label": label})
    if sample and sample < len(rows):
        rng = random.Random(seed)
        rows = rng.sample(rows, sample)
    return rows


def single_call(
    model: str,
    sample: dict[str, Any],
    retries: int = 2,
    timeout: float = 600.0,
    base_url: str = BASE_URL,
) -> dict[str, Any]:
    """Call the OpenAI-compatible proxy once and return a normalized record."""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你是企业支持 Agent，负责知识库问答、工单查询、升级建议。"},
            {"role": "user", "content": sample["text"]},
        ],
        "tools": _TOOLS,
        "tool_choice": "auto",
        "reasoning_effort": "high",
        "max_context_tokens": "1M",
        "user": f"bench-{model}-{sample.get('type', 'x')}",
    }
    req = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    for attempt in range(retries + 1):
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                r = json.loads(resp.read().decode("utf-8"))
            dt = time.time() - t0
            msg = r["choices"][0]["message"]
            usage = r.get("usage", {})
            tool_names = [tc.get("function", {}).get("name", "") for tc in (msg.get("tool_calls") or [])]
            content = str(msg.get("content", "") or "")
            return {
                "ok": True,
                "latency": dt,
                "tool_calls": tool_names,
                "content_len": len(content.strip()),
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
                "error": None,
                **sample,
            }
        except urllib.error.HTTPError as exc:
            if exc.code == 502 and attempt < retries:
                time.sleep(2 * (attempt + 1))
                continue
            return {"ok": False, "latency": time.time() - t0, "tool_calls": [], "content_len": 0,
                    "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "error": f"HTTP {exc.code}", **sample}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "latency": time.time() - t0, "tool_calls": [], "content_len": 0,
                    "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "error": str(exc)[:150], **sample}
    return {"ok": False, "latency": 0.0, "tool_calls": [], "content_len": 0, "prompt_tokens": 0,
            "completion_tokens": 0, "total_tokens": 0, "error": "retries exhausted", **sample}
