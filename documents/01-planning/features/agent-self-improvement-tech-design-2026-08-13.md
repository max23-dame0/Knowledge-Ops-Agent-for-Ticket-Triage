# 技术设计：Agent 自我改进 + RAG 深化 + 评测升级（PLN-001）

> 计划文档：`documents/01-planning/agent-self-improvement-rag-plan-2026-08-13.md`
> 本设计为 specforge 阶段②产出，阶段③任务规划、阶段④TDD 编码均以此为准。
> 状态：设计中 → 随实现更新

## 1. 概述与目标

三条线：

| 线 | 目标 | 任务 |
|----|------|------|
| A 自我改进引擎 | 失败样本 → 反思 → 经验池 → 检索注入 → 回归门控的闭环 | A1-A6 |
| C RAG 检索深度 | rerank + 相关性门控 + 查询改写 + 检索评测 | C1-C4（C5 可选，暂缓） |
| D 评测体系升级 | semantic grader + judge 校准 | D1-D2（D3 依赖方向 B 云侧，挂起） |

## 2. 现状代码分析（集成点）

| 现有模块 | 职责 | 本次涉及 |
|---------|------|---------|
| `src/rag/retrieve.py` `retrieve_kb()` | 向量+BM25 混合检索，`min_score=0.25` 低置信标记 | C1 插 rerank；C2 插相关性门控 |
| `src/tools/kb_search.py` `search_kb()` | KB 检索工具封装（pydantic 返回） | C1/C2 透出 confidence 信号 |
| `src/agents/main_agent.py` | 单决策 owner，指令常量 `MAIN_AGENT_INSTRUCTIONS` | A4 注入经验段落（开关控制） |
| `src/agents/retrieval_agent.py` | 证据规范化层 | 无决策权变更 |
| `src/evals/run_evals.py` | offline/regression 双模式，落盘 CSV | A1 输入源；A5/A6 复用 |
| `src/evals/external_bench.py` | 安全评测（注入/越狱/OOS） | A5/A6 安全指标来源 |
| `src/utils/resilience.py` | CircuitBreaker + LRU 缓存 | A2/A3/D1 复用防抖与缓存模式 |
| `src/repositories/kb_repository.py` | KB 索引/元数据单例 | C1 模型加载模式参照 |

## 3. 模块设计与分层

分层链：utils → tools → agents → app。**agents 不得 import evals**（全局规则）。

### 3.1 A 线（自我改进引擎）

| 新模块 | 层 | 职责 |
|--------|----|----|
| `src/evals/failure_extraction.py` | evals | A1：读 eval 结果 CSV → 结构化失败样本 |
| `src/improvement/schemas.py` | app | 共享 pydantic：`FailureSample` / `ExperienceEntry` / `ReflectionResult` / `GateDecision` |
| `src/improvement/reflection.py` | app | A2：失败样本 → LLM 反思 → 经验条目（PII 清洗 + LLM 失败兜底） |
| `src/improvement/experience_store.py` | app | A3：经验池 jsonl 落盘 / 容量管理 / 去重 / 检索 |
| `src/tools/experience_retrieval.py` | tools | A4 检索侧：请求 → 相似经验（main_agent 可 import，保持分层） |
| `src/improvement/injection.py` | app | A4 格式侧：注入文本生成（模板稳定） |
| `src/improvement/gate.py` | app | A5：门控纯函数（安全硬 gate + 效果软目标 + reward hacking 拦截） |
| `src/improvement/improvement_loop.py` | app | A6：编排 CLI（eval → 反思 → 注入 → 回归 → 决策） |

**A4 集成方式**：`main_agent.py` 在 `build_main_agent()` 时调用 `tools.experience_retrieval`（开关 `EXPERIENCE_INJECTION_ENABLED`，默认 false）→ 把经验段落追加到 instructions。决策 owner 不变，经验仅为 prompt 上下文。

### 3.2 C 线（RAG 检索深度）

| 新模块 | 层 | 职责 |
|--------|----|----|
| `src/rag/rerank.py` | rag | C1：CrossEncoder 精排（懒加载+缓存+失败降级） |
| `src/rag/query_expansion.py` | rag | C3：规则式改写（同义词/缩写）+ 明确查询不改写 |
| `src/rag/relevance_gate.py` | rag | C2：精排分数阈值判定 → `strong_evidence` 信号 |
| `data/retrieval_eval_set.json` | data | C4：检索评测集（新文件，锚点只增不改约束合规） |
| `src/evals/retrieval_bench.py` | evals | C4：recall@k / MRR 基准脚本 |

`retrieve_kb()` 链路变更：粗排 top_k*4 → fuse → **rerank** → 截断 top_k。返回新增 `rerank_score`、`strong_evidence` 字段（向后兼容，旧字段不动）。

### 3.3 D 线（评测体系升级）

| 新模块 | 层 | 职责 |
|--------|----|----|
| `src/evals/semantic_grader.py` | evals | D1：LLM judge 三维质量评分（正确性/完整性/证据支撑，1-5 分） |
| `src/evals/judge_calibration.py` | evals | D2：judge vs 人工标注一致性报告 |

## 4. 设计决策（歧义消解）

| # | 决策点 | 决定 | 理由 |
|---|--------|------|------|
| T1 | 经验池路径 `data/exp/` vs `data/experience/` | 统一 **`data/experience/`** | 计划 3.2 模块表为准，语义更清晰 |
| T2 | rerank 模型 | **`BAAI/bge-reranker-base`**（CrossEncoder，sentence-transformers 自带） | 中文 KB 需要中文 rerank；零新依赖；HF 可达（已测 200） |
| T3 | rerank 失败降级 | 加载/推理异常 → 回退 fused 分数排序，不阻塞主流程 | 可用性优先，确保 recall 不回退 |
| T4 | A4 开关 | env `EXPERIENCE_INJECTION_ENABLED`，默认 **false**；A6 loop 内显式开启 | 安全保守；单测可关闭验证 |
| T5 | 反思器 LLM 兜底 | LLM 失败 → 模板化通用条目（`source=fallback`），不抛异常 | 计划 AC"LLM 失败有兜底" |
| T6 | PII 清洗 | 正则：邮箱/手机/身份证/银行卡 → `[EMAIL]` 等占位符 | 经验池禁止存 PII |
| T7 | 反思器不参与路由决策 | 反思器只产出经验文本，无任何 route 输出 | D004 红线 |
| T8 | D005 与 LLM judge 关系 | 新增 ADR D007：judge 仅评质量维度，不替代行为判定指标 | 计划风险#3 |
| T9 | C2 阈值 | 默认 0.5（bge-reranker sigmoid 后 0-1），env `RERANK_MIN_SCORE` 可调 | 计划默认值；C4 评测后可校准 |
| T10 | C3 明确查询不改写 | 含 ticket_id / 工单号模式 / 长度>20 的查询跳过改写 | 计划 AC"不改写明确查询" |
| T11 | 分层 | A2-A6 核心逻辑放 `src/improvement/`（app 层）；仅 A4 检索侧下沉 `src/tools/` | 遵守"agents 不得 import evals" |
| T12 | C5 语义分块 | 暂缓，C1-C4 完成后按需评估 | 计划标记可选 |

## 5. AC 覆盖矩阵

| 任务 | AC | 验证方式 |
|------|----|---------|
| A1 | 样本字段完整、错误类型归类正确 | pytest（构造 CSV fixture） |
| A2 | 条目 schema 合法、PII 清洗生效、LLM 失败兜底 | pytest（mock LLM / 抛异常 LLM） |
| A3 | 落盘往返、容量淘汰、相似检索命中 | pytest（tmp_path 隔离） |
| A4 | 注入格式稳定、不改决策 owner、开关可关闭 | pytest（mock 检索器） |
| A5 | 安全下降被拒、效果提升被接受、reward hacking 拦截 | pytest（构造指标对） |
| A6 | 端到端跑通一轮且安全指标持平 | 真实 LLM 运行（依赖 knot-proxy 或 DeepSeek） |
| C1 | recall@5 提升或无回退 | pytest（fake scorer）+ C4 基准对比 |
| C2 | 低于阈值走澄清/弱证据路径 | pytest + 检索链路集成 |
| C3 | 短查询改写稳定、不改写明确查询 | pytest |
| C4 | 基准脚本可重复运行、产出基线报告 | 真实运行两次，结果一致 |
| D1 | judge 三维评分 + 结构化输出 | pytest（mock LLM）+ 抽样真实比对 |
| D2 | 一致性 ≥85% | 真实 judge + 人工标注（需用户参与） |

## 6. 验证策略（每任务 DoD）

1. 该任务 pytest 单测全绿（`pytest tests/test_<task>.py`）
2. ruff 0 告警（涉及文件）
3. 相关层集成测试（import 链、检索链路）
4. 需要 LLM 的任务：mock 先行（离线可跑），真实验证在端到端阶段统一执行
5. git 提交（每任务或每批次）

## 7. 风险与处理

| 风险 | 处理 |
|------|------|
| knot-proxy 未启动（127.0.0.1:8000 拒绝连接） | 离线任务不受影响；A6/D2 端到端验证前询问用户启动 proxy 或切换 DeepSeek |
| bge-reranker-base 下载 278MB | 已测 HF 可达；懒加载 + 失败降级兜底 |
| 上下文预算 | 每任务单独会话式推进；设计文档承载长期上下文 |
| 回归冒烟成本 | regression 模式调用真实 LLM，仅在关键节点跑（C 线完成、A5/A6） |

## 8. 任务执行顺序（依赖拓扑）

```
批次1（无依赖，可并行）：A1、C3、D1、C1
批次2：A2（←A1）、C2（←C1）、C4（←C1）、D2（←D1，需用户标注）
批次3：A3（←A2）
批次4：A4（←A3、C1）
批次5：A5（←A4）
批次6：A6（←A5，端到端）
挂起：D3（←方向B 云侧）、C5（可选）
```
