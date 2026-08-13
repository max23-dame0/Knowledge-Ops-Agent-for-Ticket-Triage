# 会话交接 — 2026-08-13

> 每次会话结束前填写。下一个会话读取本文件快速恢复上下文。
> 来源：L05 跨会话连续性 + L12 清洁状态

---

## 本轮做了什么

PLN-001（Agent 自我改进 + RAG 深化 + 评测升级）主体交付完成，13 个任务中 11 个完成并提交：

- **A 线（自我改进引擎，6/6）**：A1 失败轨迹采集器 → A2 反思器（PII 清洗+LLM 兜底）→ A3 经验池（jsonl/容量/去重/检索）→ A4 检索增强注入（env 开关，默认关，已集成 main_agent）→ A5 门控（安全硬 gate + 防 reward hacking）→ A6 自动迭代 loop（collect-reflect-store 编排）
- **C 线（RAG 检索深度，4/4）**：C1 CrossEncoder rerank（bge-reranker-base，懒加载+失败降级）→ C2 相关性门控（阈值 0.5，strong/weak 信号）→ C3 查询改写（规则式同义词/缩写）→ C4 检索评测集（20 条标注）+ recall@k/MRR 基准脚本
- **D 线（评测升级，1/3）**：D1 semantic grader（三维质量评分，mock 验证）；D2 待人工标注；D3 挂起等方向 B
- ADR D007 已新增（judge 仅评质量维度，不替代行为判定）
- 文档：技术设计 + 交付报告 + 检索基线报告落 documents/

关键成果：**rerank 使 recall@1 从 0.90 提升到 1.00、MRR 从 0.95 到 1.00（无回退）**；233 单测全绿（+69 新增），ruff 0 告警。

## 清洁状态检查

| 检查项 | 状态 |
|--------|:--:|
| pytest tests/（238 passed） | ✅ |
| ruff check src tests app.py | ✅ 0 告警 |
| A6 真实端到端（DeepSeek 远程端点，全链路） | ✅ 跑通，安全持平，门控拒绝 |
| offline eval（66 条，DeepSeek 远程） | ✅ route 97.0% 基线（092630/093344 两轮） |
| git status | ⚠️ 有用户并行未提交改动（见下） |
| PROGRESS.md 已更新 | ✅ |
| WIP 登记 | ✅ |

## 未提交改动清单（工作区现状）

**我（agent）的 PLN-001 代码**：已全部 commit（f795876→b945d85 共 9 个 commit）。

**用户并行改动（未提交，勿动，等用户处理）**：
- `.env.example` + `src/utils/config.py`：新增 EMBEDDING_API_KEY/BASE_URL/MODEL_ID 配置
- `src/rag/embedding.py`（新文件）：远程 Embedding API（SiliconFlow bge-m3）+ 本地 fallback 统一客户端
- `src/rag/build_index.py` / `src/repositories/kb_repository.py`：改用 embedding client
- `data/index/kb_index.faiss`：索引已用 bge-m3 重建（31KB→316KB）
- 文档：DECISIONS.md（D007，我的改动）、PROGRESS.md（我的改动）、documents/01-planning/features/（我的技术设计）

> 注意：ruff 报的 retrieve.py import 排序问题已由我修复；我的 rerank/查询改写代码与 embedding 改动兼容（233 测试全绿）。

## 仍损坏或未完成

1. **A6 预检层修复后可复跑**：真实端到端已跑通（DeepSeek 远程端点），但 3 条失败样本（E009/E035/E049）都在规则预检层，注入不可达 → fixed=0 → 门控如实拒绝。修 `_maybe_clarify` 政策类误判 + E049 eval 口径后可复跑，预期 ACCEPT。
2. **D2 judge 校准**：需用户人工标注约 10-20 条 kb 样本的三维评分，一致性 ≥85% 才启用。
3. **D3 / C5**：等方向 B 产出 / 按需推进。
4. **fabrication 度量细化**：route=kb 但 conclusion 拒答应视为拒答（对齐 external_bench `_is_refused`）。

## 下一步最佳动作

1. 修预检层：`_maybe_clarify` 对"什么情况下必须升级"类政策问题不应澄清（补 ESCALATION_POLICY_HINTS 完整模式）；E049 eval 口径（refuse 时 evidence 不应判冲突）→ 复跑 A6 迭代看门控是否 ACCEPT
2. D2：抽 10-20 条 kb 样本，跑 judge + 用户人工标注，比对一致性写校准报告
3. 用户 review 并提交其 embedding API 并行改动（或让我合并提交）

## 重要上下文（给下一个会话的笔记）

- PLN-001 计划：`documents/01-planning/agent-self-improvement-rag-plan-2026-08-13.md`；技术设计（含 T1-T12 决策）：`documents/01-planning/features/agent-self-improvement-tech-design-2026-08-13.md`
- 分层：improvement 逻辑在 `src/improvement/`（app 层）；经验检索在 `src/tools/experience_retrieval.py`（agents 可 import）；A1 采集在 evals 层
- A4 注入开关：env `EXPERIENCE_INJECTION_ENABLED`，默认关；注入文本无 markdown 标题、无路由指令（D004）
- 经验池：`data/experience/experiences.jsonl`（gitignore 应排除——检查 .gitignore！）
- 检索链路新增字段：`rerank_score`、`strong_evidence`（向后兼容，旧调用方不受影响）
- rerank 模型：BAAI/bge-reranker-base（CrossEncoder，懒加载，失败回退 fused 排序）
- 注意用户并行改动：远程 embedding（bge-m3）支持未提交，跑 eval 前确认索引模型与检索模型一致

## 常用命令

```bash
.venv\Scripts\python.exe -m pytest tests/                          # 233 passed
.venv\Scripts\python.exe -m ruff check src tests app.py            # 0 告警
.venv\Scripts\python.exe -m src.evals.retrieval_bench              # 检索基线（rerank）
.venv\Scripts\python.exe -m src.evals.retrieval_bench --no-rerank  # 基线对比
.venv\Scripts\python.exe -m src.improvement.improvement_loop --eval-result-csv data/eval_results/xxx.csv  # A6 loop
```
