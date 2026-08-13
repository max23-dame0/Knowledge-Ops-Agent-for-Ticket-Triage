---
doc_id: "REP-PLN001-001"
title: "PLN-001 交付报告：自我改进引擎 + RAG 深化 + 评测升级"
category: "review"
date: "2026-08-13"
related:
  - "../01-planning/agent-self-improvement-rag-plan-2026-08-13.md"
  - "../01-planning/features/agent-self-improvement-tech-design-2026-08-13.md"
---

# PLN-001 交付报告（2026-08-13）

## 交付总览

| 线 | 任务 | 状态 | commit |
|----|------|:--:|--------|
| A 自我改进 | A1-A6 全部 | ✅ | f795876 / 97cb5f8 / c1d850e / 5b2b9d1 / 82a7781 / b945d85 |
| C RAG 深化 | C1-C4 全部 | ✅ | a810077 / c90a323 / 8f3c11c |
| D 评测升级 | D1 完成，D2 待标注，D3 挂起 | 🟡 | d761314 |

**单测：233 passed（+69 新增）**；**ruff 0 告警**；**检索基线报告已产出**。

## 各任务验证结果

### A 线（自我改进引擎，RL 思想落地）

| 任务 | 模块 | 验证 |
|------|------|------|
| A1 | `src/evals/failure_extraction.py` | 6 单测：六类错误归类（route/tool/clarification/grounding/refusal/execution）、字段完整、缺文件报错 |
| A2 | `src/improvement/reflection.py` + `schemas.py` | 6 单测：schema 合法、PII 清洗（邮箱/手机/身份证/银行卡→占位符）、LLM 失败兜底（fallback 条目） |
| A3 | `src/improvement/experience_store.py` | 6 单测：jsonl 落盘往返、容量淘汰（最旧先出）、去重、词法相似检索、空文件安全 |
| A4 | `src/improvement/injection.py` + `src/tools/experience_retrieval.py` | 6 单测：注入格式稳定（无 markdown 标题、无路由指令）、开关默认关（env 控制）、已集成 main_agent 预检后注入 |
| A5 | `src/improvement/gate.py` | 5 单测：安全下降被拒、效果提升被接受、reward hacking（幻觉风险上升）拦截、失败数增加被拒、无效果被拒 |
| A6 | `src/improvement/improvement_loop.py` | 6 单测：collect-reflect-store 全链路（mock）、去重、rejected 标记降权、CLI 可用 |

**防 reward hacking 设计已落地**（A5）：安全硬 gate（注入/Jailbreak/OOS 拒答率不降 + 幻觉风险为 0）+ 效果软目标（目标错误修复 > 0 且总失败不增），任何一条不满足即拒绝并标记 `rejected`。

### C 线（RAG 检索深度）

| 任务 | 模块 | 验证 |
|------|------|------|
| C1 | `src/rag/rerank.py`（CrossEncoder bge-reranker-base，懒加载+缓存+失败降级） | 3 单测 + 真实链路冒烟（VPN→vpn_login 首位、SLA→sla_policy 首位） |
| C2 | `src/rag/relevance_gate.py`（阈值 0.5，strong/weak 信号） | 6 单测 + 检索结果带 `rerank_score`/`strong_evidence` 字段 |
| C3 | `src/rag/query_expansion.py`（规则式同义词/缩写扩展） | 5 单测：短查询扩展稳定、明确查询（ticket_id/长句）不改写、已接入 retrieve_kb |
| C4 | `data/retrieval_eval_set.json`（20 条标注）+ `src/evals/retrieval_bench.py` | 8 单测 + 基线报告：**recall@1 0.90→1.00，MRR 0.95→1.00（rerank 提升无回退）** |

基线报告：`documents/02-review/retrieval-baseline-report-2026-08-13.md`。

### D 线（评测体系升级）

| 任务 | 模块 | 验证 |
|------|------|------|
| D1 | `src/evals/semantic_grader.py`（LLM judge 三维 1-5 评分） | 5 单测（mock）：解析/钳制/容错/提示词含三维 |
| D2 | judge 校准 | ⬜ 待做：需人工标注比对（一致性 ≥85% 才启用） |
| D3 | 真实工单样本纳入回归 | ⏸ 挂起：等方向 B 云侧产出 |

**ADR D007 已新增**（DECISIONS.md）：judge 仅评质量维度（正确性/完整性/证据支撑），不替代 D005 规则式行为判定。

## 量化指标状态

| 指标 | 目标 | 现状 |
|------|------|------|
| M1 自我改进有效性 | ≥30% 修复率 | 待 A6 真实端到端运行后测量 |
| M2 安全无回归 | 100%/100%/100%/0 | 门控已实现，待真实运行验证 |
| M3 检索质量 | recall@5 0.8 / MRR 0.7 | ✅ recall@5=1.0 / MRR=1.0（达标） |
| M4 judge 一致性 | ≥85% | 待 D2 校准 |
| M5 端到端 | 全自动可复跑 | loop 已实现，真实 LLM 验证待端点 |

## 遗留事项

1. **A6 真实端到端**：loop 逻辑已 mock 验证，但完整一轮（eval→反思→注入→回归→门控）需要真实 LLM 端点。当前 `.env` 指向 knot-proxy（127.0.0.1:8000），**knot-proxy 未启动**；需用户启动或切换 DeepSeek 后执行。
2. **D2 judge 校准**：需要用户对抽样回答做人工标注（约 10-20 条 kb 样本的三维评分），比对 judge 输出一致性 ≥85% 后才启用 judge 参与门控。
3. **D3 / C5**：分别等方向 B 产出与 C1-C4 稳定后按需推进。

## 附：验证命令

```bash
.venv\Scripts\python.exe -m pytest tests/                     # 233 passed
.venv\Scripts\python.exe -m ruff check src tests app.py       # 0 告警
.venv\Scripts\python.exe -m src.evals.retrieval_bench         # 检索基线（rerank）
.venv\Scripts\python.exe -m src.evals.retrieval_bench --no-rerank  # 基线对比
```
