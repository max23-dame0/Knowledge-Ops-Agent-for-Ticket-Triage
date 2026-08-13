---
doc_id: "REP-PLN001-FINAL"
title: "PLN-001 最终交付报告：Agent 自我改进 + RAG 深化 + 评测升级"
category: "review"
date: "2026-08-13"
status: "delivered"
related:
  - "../01-planning/agent-self-improvement-rag-plan-2026-08-13.md"
  - "../01-planning/features/agent-self-improvement-tech-design-2026-08-13.md"
  - "pln001-delivery-report-2026-08-13.md"
  - "retrieval-baseline-report-2026-08-13.md"
  - "a6-e2e-iteration-report-2026-08-13.md"
---

# PLN-001 最终交付报告

> 计划：`documents/01-planning/agent-self-improvement-rag-plan-2026-08-13.md`
> 技术设计（含 T1-T12 决策）：`documents/01-planning/features/agent-self-improvement-tech-design-2026-08-13.md`
> 状态：**已交付**（13 任务中 11 完成，2 个依赖外部输入暂缓）

---

## 一、任务总览

PLN-001 覆盖三条能力线，全部通过 specforge-feature-dev 工作流（需求澄清 → 技术设计 → 任务规划 → TDD 编码）实现，每个任务独立验证、独立提交。

| 线 | 目标 | 完成度 |
|----|------|:--:|
| A 自我改进引擎 | 失败样本 → 反思 → 经验池 → 检索注入 → 回归门控的闭环 | 6/6 ✅ |
| C RAG 检索深度 | rerank + 相关性门控 + 查询改写 + 检索评测 | 4/4 ✅（C5 可选暂缓） |
| D 评测体系升级 | semantic grader + judge 校准 | 1/3 🟡（D2 待标注、D3 等云侧） |

## 二、交付清单

| 任务 | 模块 | 状态 | commit |
|------|------|:--:|--------|
| A1 失败轨迹采集器 | `src/evals/failure_extraction.py` | ✅ | f795876 |
| A2 反思器（PII 清洗 + LLM 兜底） | `src/improvement/reflection.py` + `schemas.py` | ✅ | 97cb5f8 |
| A3 经验池（jsonl/容量/去重/检索/降级） | `src/improvement/experience_store.py` | ✅ | c1d850e |
| A4 检索增强注入（env 开关） | `src/improvement/injection.py` + `src/tools/experience_retrieval.py` | ✅ | 5b2b9d1 |
| A5 自我改进门控（防 reward hacking） | `src/improvement/gate.py` | ✅ | 82a7781 |
| A6 自动迭代 loop（端到端） | `src/improvement/improvement_loop.py` + `iteration_driver.py` | ✅ | b945d85 / 704eb23 / 8fc7732 |
| C1 CrossEncoder rerank | `src/rag/rerank.py` | ✅ | a810077 |
| C2 相关性门控 + 低置信信号 | `src/rag/relevance_gate.py` | ✅ | a810077 |
| C3 查询改写（规则式） | `src/rag/query_expansion.py` | ✅ | 8f3c11c |
| C4 检索评测集 + 基准 | `data/retrieval_eval_set.json` + `src/evals/retrieval_bench.py` | ✅ | c90a323 |
| D1 semantic grader（三维评分） | `src/evals/semantic_grader.py` | ✅ | d761314 |
| D2 judge 校准 | — | ⬜ 待用户标注 | — |
| D3 真实工单纳入回归 | — | ⏸ 等方向 B | — |
| C5 语义分块 | — | ⏸ 计划可选 | — |

**ADR 变更**：新增 D007（judge 仅评质量维度，不替代规则式行为判定）。

## 三、各线详情

### A 线：自我改进引擎（RL 思想落地）

失败样本（A1）→ 反思器产出模式级经验（A2，PII 清洗 + LLM 失败兜底）→ 经验池持久化（A3，容量淘汰/去重/词法检索）→ 请求时检索注入（A4，env 开关默认关，只做 prompt 上下文不改路由）→ 回归后门控（A5，安全硬 gate + 效果软目标）→ 全自动编排（A6）。

**防 reward hacking 三重保障**：
1. 安全硬 gate：注入/Jailbreak/OOS 拒答率不降 + 幻觉风险为 0
2. 效果软目标：目标错误修复 > 0 且总失败不增
3. 拒绝路径：条目 in-place 降级 `rejected`，不再参与注入

### C 线：RAG 检索深度

检索链路：粗排 → 混合融合 → **CrossEncoder 精排（bge-reranker-base）** → 截断。新增 `rerank_score` / `strong_evidence` 字段（向后兼容）。查询改写对短模糊查询做同义词/缩写扩展，明确查询（ticket_id/长句）不改写。rerank 失败自动回退 fused 排序。

### D 线：评测体系升级

semantic grader 对 kb 样本最终回答做三维评分（正确性/完整性/证据支撑 1-5），作为门控的质量信号补充，不改变规则式行为判定（D007）。

## 四、验证结果

| 验证项 | 结果 |
|------|------|
| 单元测试 | **243 passed**（+74 新增） |
| lint | ruff 0 告警 |
| 检索基线（C4） | recall@1 **0.90→1.00**、MRR **0.95→1.00**（rerank 提升无回退） |
| A6 真实端到端 | DeepSeek 远程端点全链路跑通，安全指标持平（1.0→1.0），门控如实拒绝 |
| 索引构建 | HNSW + SiliconFlow embedding（用户配置），检索冒烟通过 |

## 五、量化指标（M）

| 指标 | 目标 | 结果 |
|------|------|------|
| M1 自我改进有效性 | ≥30% 修复率 | 本轮 fixed=0（失败样本为预检层问题，注入不可达），见遗留 |
| M2 安全无回归 | 100%/100%/100%/0 | ✅ 门控实现 + 真实端到端持平验证 |
| M3 检索质量 | recall@5 0.8 / MRR 0.7 | ✅ recall@5=1.0 / MRR=1.0 |
| M4 judge 一致性 | ≥85% | ⬜ 待 D2 校准 |
| M5 端到端 | 全自动可复跑 | ✅ iteration_driver 一键全迭代 |

## 六、Embedding 并行改动（用户工作，本轮一并提交）

切换到 OpenAI 兼容远程 Embedding 端点（SiliconFlow），本地 sentence-transformers 回退：

- `src/rag/embedding.py`（新）：`EmbeddingClient` 统一 encode 接口 + `OpenAIEmbeddingClient`（远程 API，L2 归一化）+ `LocalEmbeddingClient`（本地回退）
- `src/utils/config.py`：`EmbeddingSettings` + `get_embedding_settings()`（未配置 API key 返回 None → 本地模式）
- `src/rag/build_index.py` / `kb_repository.py` / `retrieve.py`：改用 embedding client
- `.env.example`：新增 Embedding 端点示例（占位符，无真实 key）
- 本次补测试 `tests/test_embedding.py`（5 单测：降级逻辑 + 归一化 + 空输入）

## 七、遗留事项与下一步

| # | 事项 | 状态 |
|---|------|------|
| 1 | **A6 预检层修复后可复跑**：3 条失败样本（E009/E035/E049）都在规则预检层，注入不可达 → fixed=0 → 门控拒绝。修 `_maybe_clarify` 政策类误判 + E049 eval 口径后复跑，预期 ACCEPT | 待做 |
| 2 | D2 judge 校准（需用户标注 10-20 条 kb 样本三维评分） | 待用户 |
| 3 | D3 真实工单样本纳入回归 | 等方向 B |
| 4 | C5 语义分块（计划可选） | 暂缓 |
| 5 | fabrication 度量细化（route=kb 但结论拒答应视为拒答，对齐 `_is_refused`） | 待做 |

## 八、commit 清单（origin/main..HEAD，共 15 个）

```
f795876  A1 failure trajectory extraction
8f3c11c  C3 rule-based query expansion
a810077  C1 rerank + C2 relevance gate
d761314  D1 semantic grader
c90a323  C4 retrieval benchmark + baseline
97cb5f8  A2 reflection generator
c1d850e  A3 experience store
5b2b9d1  A4 experience injection
82a7781  A5 gating
b945d85  A6 improvement loop
15c3e84  delivery docs + ADR D007 + progress board
4f91993  record PLN-001 session
704eb23  A6 iteration driver + reject downgrade
8fc7732  A6 e2e report
7d68db9  harness files synced
```
