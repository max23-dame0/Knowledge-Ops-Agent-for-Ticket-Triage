---
doc_id: "REP-C4-001"
title: "KB 检索质量基线报告（C4，2026-08-13）"
category: "review"
date: "2026-08-13"
related:
  - "../01-planning/agent-self-improvement-rag-plan-2026-08-13.md"
---

# KB 检索质量基线报告（C4）

## 结论

CrossEncoder rerank（C1，`BAAI/bge-reranker-base`）接入后，检索质量**提升且无回退**：

| 指标 | 无 rerank（基线） | 有 rerank | 变化 |
|------|:--:|:--:|:--:|
| recall@1 | 0.90 | **1.00** | +0.10 |
| recall@3 | 1.00 | 1.00 | 持平 |
| recall@5 | 1.00 | 1.00 | 持平 |
| MRR | 0.95 | **1.00** | +0.05 |

- 评测集：`data/retrieval_eval_set.json`（20 条 query，覆盖 10 篇 KB 文档，文档级相关标注）
- 脚本：`src/evals/retrieval_bench.py`（`--no-rerank` 可复现基线对比）
- 指标目标（M3）：基线已建立，recall@5=1.0 / MRR=1.0，超过参考阈值（0.8 / 0.7）

## 可复现命令

```bash
.venv\Scripts\python.exe -m src.evals.retrieval_bench            # rerank 开启
.venv\Scripts\python.exe -m src.evals.retrieval_bench --no-rerank  # 基线对比
```

## 备注

- rerank 失败时自动回退 fused 排序（`src/rag/rerank.py` 降级路径），不阻塞检索。
- C2 相关性门控阈值默认 0.5（`DEFAULT_RERANK_THRESHOLD`），低于阈值的命中标记 `weak_evidence`。
- 真实链路冒烟：VPN 查询 vpn_login 稳居首位；SLA 查询 sla_policy 首位。
