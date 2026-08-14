"""Unified benchmark configuration for the enterprise-ticket eval system.

Central definition of datasets, tasks, metrics, and baselines so every eval
component (tool-behavior, classification, routing) shares one source of truth.
"""
from __future__ import annotations

from pathlib import Path

# ---------- Paths ----------
# __file__ = <root>/src/evals/ticket_bench/bench_config.py -> parents[3] = project root
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATASET_DIR = PROJECT_ROOT / "data" / "eval_datasets"
OUTPUT_DIR = PROJECT_ROOT / "data" / "eval_results"

TOBI_PATH = DATASET_DIR / "tobi_tickets" / "dataset-tickets-multi-lang-4-20k.csv"
ITSM_PATH = DATASET_DIR / "itsm_tickets" / "train.jsonl"

# ---------- Datasets ----------
DATASETS = {
    "tobi": {
        "name": "Tobi-Bueck 客服工单",
        "path": TOBI_PATH,
        "valid_rows": 18537,
        "supervised": True,
        "official_fields": ["type", "priority", "queue", "language", "tag_1..8"],
    },
    "itsm": {
        "name": "alezzandro/itsm_tickets",
        "path": ITSM_PATH,
        "valid_rows": 900,
        "supervised": True,
        "label_meaning": {0: "other", 1: "ticket", 2: "inquiry"},
    },
}

# ---------- Tobi classification tasks (official GT) ----------
TOBI_CLASSIFY_TASKS = {
    "type": {
        "label": "type",
        "classes": ["Incident", "Request", "Problem", "Change"],
        "prompt": "对以下客服工单进行分类，只能输出一个词：Incident、Request、Problem 或 Change。不要输出其他内容。",
    },
    "priority": {
        "label": "priority",
        "classes": ["low", "medium", "high"],
        "prompt": "对以下客服工单的紧急程度进行分类，只能输出一个词：low、medium 或 high。不要输出其他内容。",
    },
    "queue": {
        "label": "queue",
        "classes": ["Technical Support", "Product Support", "Customer Service", "IT Support",
                    "Billing and Payments", "Returns and Exchanges", "Service Outages and Maintenance",
                    "Sales and Pre-Sales", "Human Resources", "General Inquiry"],
        "prompt": "对以下客服工单进行部门路由分类，只能输出以下队列名之一：Technical Support、Product Support、Customer Service、IT Support、Billing and Payments、Returns and Exchanges、Service Outages and Maintenance、Sales and Pre-Sales、Human Resources、General Inquiry。不要输出其他内容。",
    },
}

# ---------- Agent tools used in behavior eval ----------
AGENT_TOOLS = [
    {"type": "function", "function": {
        "name": "get_ticket_status",
        "description": "按 ticket_id 查询工单状态",
        "parameters": {"type": "object", "properties": {"ticket_id": {"type": "string"}}, "required": ["ticket_id"]},
    }},
    {"type": "function", "function": {
        "name": "search_kb",
        "description": "Search the local knowledge base for grounded support evidence.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}, "top_k": {"type": "integer"}}, "required": ["query"]},
    }},
    {"type": "function", "function": {
        "name": "create_escalation_draft",
        "description": "Generate a structured escalation suggestion.",
        "parameters": {"type": "object", "properties": {"issue_summary": {"type": "string"}, "evidence": {"type": "array", "items": {"type": "string"}}}, "required": ["issue_summary"]},
    }},
]

# ---------- Baselines (no LLM, for context) ----------
def majority_baseline(row_count: int, classes: list[str], labels: list[str]) -> dict:
    """Baseline: always predict the most frequent class. Returns {accuracy, n}."""
    from collections import Counter
    if not labels:
        return {"accuracy": 0.0, "n": row_count}
    most_common = Counter(labels).most_common(1)[0][0]
    acc = labels.count(most_common) / max(len(labels), 1)
    return {"accuracy": round(acc, 4), "n": row_count}


def random_baseline(row_count: int, n_classes: int) -> dict:
    """Baseline: uniform random guess."""
    return {"accuracy": round(1.0 / max(n_classes, 1), 4), "n": row_count}
