"""Benchmark report generator: aggregate per-model results into a solid report.

Reads all result JSONs under data/eval_results matching the naming convention
produced by run_full.py / run_classify.py, and renders:
- markdown report (data/eval_results/benchmark_report_{stamp}.md)
- machine-readable JSON (data/eval_results/benchmark_report_{stamp}.json)

Also computes majority/random baselines for classification tasks so a model's
numbers are interpreted against a reference, not in a vacuum.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .bench_config import DATASETS, OUTPUT_DIR, TOBI_CLASSIFY_TASKS

FULL_PATTERN = "ticket_full_*.json"
CLASSIFY_PATTERN = "ticket_classify_*.json"

# mapping: task result file -> (dataset, task, is_supervised)
def classify_results() -> list[dict[str, Any]]:
    out = []
    for p in sorted(OUTPUT_DIR.glob(CLASSIFY_PATTERN)):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        for task, r in data.items():
            out.append({"source": p.stem, "model": r.get("model", "?"),
                        "task": r.get("task", task), "dataset": "tobi",
                        "accuracy": r.get("accuracy"), "success_rate": r.get("success_rate"),
                        "ok_count": r.get("ok_count"), "confusion": r.get("confusion", {})})
    return out


def full_results() -> list[dict[str, Any]]:
    out = []
    for p in sorted(OUTPUT_DIR.glob(FULL_PATTERN)):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        for ds, r in data.items():
            if not isinstance(r, dict):
                continue
            out.append({"source": p.stem, "model": r.get("model", "?"),
                        "dataset": r.get("dataset", ds),
                        **{k: v for k, v in r.items() if k not in ("dataset", "model")}})
    return out


def _load_tobi_labels() -> dict[str, list[str]]:
    import pandas as pd
    df = pd.read_csv(DATASETS["tobi"]["path"])
    df = df.dropna(subset=["subject", "body", "type", "priority", "queue"])
    return {
        "type": [str(x).strip() for x in df["type"]],
        "priority": [str(x).strip().lower() for x in df["priority"]],
        "queue": [str(x).strip() for x in df["queue"]],
    }


def render_compare(models: list[str], classify: list[dict], full: list[dict]) -> str:
    from collections import defaultdict
    lines: list[str] = []
    labels = _load_tobi_labels()

    # ---- classification table ----
    lines.append("## Tobi 有监督分类（官方 GT）\n")
    by_task: dict[str, dict[str, float]] = defaultdict(dict)
    for r in classify:
        by_task[r["task"]][r["model"]] = r.get("accuracy")
    for task, cfg in TOBI_CLASSIFY_TASKS.items():
        classes = cfg["classes"]
        n_classes = len(classes)
        gt_labels = labels.get(task, [])
        maj = Counter(gt_labels).most_common(1)[0][1] / max(len(gt_labels), 1)
        lines.append(f"### {task}（{n_classes} 类）\n")
        lines.append(f"| 模型 | accuracy | vs 多数类基线 | vs 随机 |")
        lines.append(f"|---|---|---|---|")
        lines.append(f"| 多数类基线 | {maj:.4f} | — | +{maj - 1/n_classes:.4f} |")
        lines.append(f"| 随机基线 | {1/n_classes:.4f} | {1/n_classes - maj:.4f} | — |")
        for model in models:
            acc = by_task.get(task, {}).get(model)
            if acc is None:
                lines.append(f"| {model} | — | — | — |")
                continue
            lines.append(f"| {model} | {acc:.4f} | {acc - maj:+.4f} | {acc - 1/n_classes:+.4f} |")
        lines.append("")

    # ---- Tobi behavior metrics ----
    lines.append("## Tobi Agent 行为（无监督）\n")
    lines.append("| 模型 | success_rate | kb_grounding | escalation | answerable | latency_p50 | delta_tok/req |")
    lines.append("|---|---|---|---|---|---|---|")
    for model in models:
        row = next((r for r in full if r["model"] == model and r["dataset"] == "tobi"), None)
        if not row:
            lines.append(f"| {model} | — | — | — | — | — | — |")
            continue
        lines.append(
            f"| {model} | {row.get('success_rate', 0):.4f} | {row.get('kb_grounding_rate', 0):.4f} "
            f"| {row.get('escalation_signal_rate', 0):.4f} | {row.get('answerable_rate', 0):.4f} "
            f"| {row.get('latency_p50', 0)}s | {row.get('avg_delta_tokens_per_req', 0)} |")
    lines.append("")

    # ---- ITSM routing ----
    lines.append("## ITSM 路由准确率（有监督）\n")
    lines.append("| 模型 | route_accuracy | success_rate |")
    lines.append("|---|---|---|")
    for model in models:
        row = next((r for r in full if r["model"] == model and r["dataset"] == "itsm"), None)
        if not row:
            lines.append(f"| {model} | — | — |")
            continue
        lines.append(f"| {model} | {row.get('route_accuracy', 0):.4f} | {row.get('success_rate', 0):.4f} |")
    lines.append("")

    # ---- latency / cost cross-model ----
    lines.append("## 性能与成本对比（Tobi 全量）\n")
    lines.append("| 模型 | throughput(rps) | latency_p50 | latency_p95 | delta_tokens/req |")
    lines.append("|---|---|---|---|---|")
    for model in models:
        row = next((r for r in full if r["model"] == model and r["dataset"] == "tobi"), None)
        if not row:
            continue
        lines.append(f"| {model} | {row.get('throughput_rps', 0)} | {row.get('latency_p50', 0)}s "
                     f"| {row.get('latency_p95', 0)}s | {row.get('avg_delta_tokens_per_req', 0)} |")
    return "\n".join(lines)


def render_report(models: list[str]) -> tuple[str, dict[str, Any]]:
    classify = classify_results()
    full = full_results()
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")

    # infer models present in results
    all_models = models or sorted({r["model"] for r in classify} | {r["model"] for r in full})

    md = ["# 企业工单评测报告", "", f"生成时间：{datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}", "",
          f"数据集：{DATASETS['tobi']['name']}（{DATASETS['tobi']['valid_rows']}）+ "
          f"{DATASETS['itsm']['name']}（{DATASETS['itsm']['valid_rows']}）", "",
          f"评测模型：{', '.join(all_models)}", ""]
    md.append(render_compare(all_models, classify, full))

    data = {
        "generated_at": datetime.now(UTC).isoformat(),
        "models": all_models,
        "classification": classify,
        "full_behavior": full,
    }
    return "\n".join(md), data


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Generate benchmark report from result JSONs.")
    parser.add_argument("--models", nargs="*", default=[], help="models to include (default: all found)")
    parser.add_argument("--out", default=None, help="output md path")
    args = parser.parse_args()

    md, data = render_report(args.models)
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    md_path = Path(args.out) if args.out else OUTPUT_DIR / f"benchmark_report_{stamp}.md"
    json_path = OUTPUT_DIR / f"benchmark_report_{stamp}.json"
    md_path.write_text(md, encoding="utf-8")
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(md)
    print(f"\nSaved: {md_path}")
    print(f"Saved: {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
