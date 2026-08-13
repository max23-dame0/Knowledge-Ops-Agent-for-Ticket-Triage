---
doc_id: ARCH-001
title: "架构说明"
category: "architecture"
role: "[State]"
status: "published"
date: "2026-08-13"
author: "knowledge-ops-agent 团队"
tags: ["architecture", "main-agent", "retrieval-agent", "rag", "routing"]
related:
  - "tools.md"
  - "evaluation.md"
  - "manual-review-checklist.md"
  - "02-review/local-endpoint-tool-eval-report-2026-08-13.md"
---

# 架构说明

> **摘要**：本项目架构的权威描述——单决策者 `main_agent` + 轻量 `retrieval_agent` 证据层 + 三个本地工具，覆盖 kb / ticket / escalation / clarify / refuse 五类路由。
> **来源**：由原 README 拆分迁移（2026-08-13 文档治理），内容与代码库保持同步。

## 目录

- [一、项目定位](#一项目定位)
- [二、为什么这是一个 Agent 项目](#二为什么这是一个-agent-项目)
- [三、架构总览](#三架构总览)
- [四、主控层：main_agent](#四主控层main_agent)
- [五、KB evidence 层：retrieval_agent](#五kb-evidence-层retrieval_agent)
- [六、KB 检索工具路径](#六kb-检索工具路径)
- [七、Ticket 与 Escalation 动作路径](#七ticket-与-escalation-动作路径)
- [八、边界规则 / 预检查层](#八边界规则--预检查层)
- [九、日志与 tracing](#九日志与-tracing)
- [十、项目结构](#十项目结构)
- [十一、已知限制](#十一已知限制)
- [十二、后续方向](#十二后续方向)

---

## 一、项目定位

`knowledge-ops-agent` 是一个小型支持运营 Agent，当前聚焦三类具体工作流：

- 基于本地 markdown 文档的知识库问答（`data/kb_docs/`）
- 基于本地 JSON 工单数据的查询（`data/tickets.json`）
- 基于问题摘要和已有证据的升级建议

当前系统以单个 `main_agent` 为核心，负责路由、澄清、拒答和工具选择。`retrieval_agent` 只挂在知识库路径下，负责包装 KB 检索并标准化 evidence，但它不负责高层决策，也不会接管主流程。

这个项目**不是 production-ready 系统**。它被刻意设计成一个可解释、可检查、便于迭代的 demo，用来展示 agent 设计、工具调用、结构化输出和 eval-driven iteration，而不是被包装成一个大型自治多 Agent 平台。

## 二、为什么这是一个 Agent 项目

这个项目不只是 FAQ 机器人、普通聊天封装或纯 RAG demo，因为系统在回答前必须做一系列受控决策。

它体现 agent 特征的地方在于：

- 能在 `kb`、`ticket`、`escalation`、`clarify`、`refuse` 之间做路由
- 会在信息不足时先澄清，而不是直接猜测
- 会对明显不安全或超范围的请求拒答
- 需要事实时会调用工具，而不是只依赖模型记忆
- 会把输出归一化为结构化 schema，方便 UI、调试和离线评测使用

知识库路径也不只是"检索然后回答"。系统在本地检索之外，还增加了一个轻量 `retrieval_agent` 层，用来把原始检索结果整理成标准化 evidence，便于主 Agent 更稳定地复用。

与此同时，这并不是一个 fully autonomous multi-agent system。`main_agent` 仍然是唯一的高层决策者，负责 route 和 tool use；`retrieval_agent` 只是受控的检索与证据整理模块；工单查询和升级建议仍由专门工具完成。更准确的描述是：**一个主 Agent + 受控子模块**，而不是一组独立 Agent 自由协作。

## 三、架构总览

```
User -> main_agent -> retrieval / ticket / escalation tool -> normalized output -> UI / CLI / eval
```

实际运行时：

1. 用户从 CLI 或 Streamlit 提交问题。
2. `main_agent` 先执行轻量 refusal / clarification 预检查。
3. `main_agent` 决定或提示 route：`kb`、`ticket`、`escalation`、`clarify`、`refuse`。
4. 如果需要 grounding，`main_agent` 再调用对应工具路径。
5. 工具输出被整理成统一结构（`AgentAnswer`），供 UI 展示和离线评测使用。

## 四、主控层：main_agent

文件：`src/agents/main_agent.py`

这是系统唯一的主控层。

职责：

- 负责 `kb / ticket / escalation / clarify / refuse` 的高层路由决策
- 在模型执行前应用轻量边界规则
- 决定什么时候该澄清，什么时候该拒答
- 通过 OpenAI Agents SDK 注册并调用工具
- 将最终回答归一化为统一字段，例如：`route`、`answer`、`conclusion`、`evidence`、`next_action`、`human_handoff`、`confidence`、`tool_calls`、`clarified`、`refused`（兼容别名字段见 `_finalize_response`）

重要边界：

- `main_agent` 仍然是唯一的高层决策者（见 DECISIONS.md D004）
- 当前项目不是一个 free-form multi-agent handoff 系统

## 五、KB evidence 层：retrieval_agent

文件：`src/agents/retrieval_agent.py`

这是一个轻量的 retrieval-and-evidence helper，**不是 routing agent**。

职责：

- 接收 KB query
- 调用已有的 `search_kb(query)` 工具
- 把原始检索命中整理成标准化 evidence
- 返回结构化 retrieval 输出，例如：`query`、`results`、`normalized_evidence`、`source_titles`

它参与的场景：

- 默认用于 KB 问答
- 在 escalation 缺少事实时，可作为补充 KB 证据的层

它**不**负责：

- 不做高层 route 决策
- 不替代 `get_ticket_status`
- 不替代 `create_escalation_draft`
- 不接管用户侧主流程

它存在的价值：

- 让 KB evidence 格式更稳定
- 减少主 Agent 内部零散的 evidence 拼装逻辑
- 让 UI 展示和 eval grounding 检查更一致

## 六、KB 检索工具路径

相关文件：

- `src/tools/kb_search.py`
- `src/rag/chunking.py`
- `src/rag/build_index.py`
- `src/rag/retrieve.py`
- `src/rag/hybrid.py`（BM25 混合检索，零依赖）

流程：

- 读取 `data/kb_docs/` 下的 markdown 文档 → 做 chunking
- 用 `sentence-transformers` 生成向量
- 用 FAISS 建立本地索引（默认 HNSW，`build_index --index_type` 可切换）
- `search_kb(query)` 负责执行底层本地检索（HNSW + BM25 混合，`min_score` 低置信标记）
- `retrieval_agent` 在主 Agent 需要 KB grounding 时，对返回结果做 evidence 标准化

本地索引文件：

- `data/index/kb_index.faiss`
- `data/index/kb_metadata.json`（**文档变更后须重建索引**）

## 七、Ticket 与 Escalation 动作路径

### Ticket 动作路径

文件：`src/tools/ticket_tools.py`

职责：

- 从 `data/tickets.json` 读取本地工单数据
- 归一化并解析 `ticket_id`（规范形 `TKT-1004`，接受 `TKT1004` / `TKT 1004` / `tkt-1004` / 裸数字）
- 返回结构化工单信息或未命中结果

这个路径用于工单状态、负责人、优先级、更新时间等查询。

### Escalation 动作路径

文件：`src/tools/escalation_tools.py`

职责：

- 接收 `issue_summary` 和可选 `evidence`
- 用简单规则生成升级建议
- 返回：`severity`、`suggested_team`、`escalation_summary`、`recommended_next_step`

这个路径用于判断一个问题是否需要升级、应该给哪个团队等。

## 八、边界规则 / 预检查层

文件：`src/agents/main_agent.py` + `src/agents/guardrails.py`

这是一层嵌在主 Agent 内部的轻量规则层，不是独立 routing agent。

当前负责：

- 在调用工具前拒答明显不安全请求（含注入 / 越狱 / 批量窃取检测，多语种 EN/DE/ES/FR）
- 对缺少 `ticket_id` 的 ticket 问题先澄清
- 让短但动作明确的 KB 问题不要被过度澄清
- 让升级政策说明问题留在 `kb`
- 让具体 escalation case 不被过早拦到 `clarify`
- escalation high/urgent 输出 `needs_human_confirmation`

## 九、日志与 tracing

相关文件：

- `src/utils/logging.py`
- `src/agents/main_agent.py`

当前会记录（统一 `key=value` 格式，`LOG_FORMAT=json` 时输出结构化日志）：

- 用户输入
- route hints
- tool 调用
- 最终回答摘要

说明：

- 当前使用标准 Python logging
- 为兼容第三方 OpenAI-compatible provider，OpenAI Agents SDK tracing 在运行时是关闭的（DECISIONS.md D006）

## 十、项目结构

```text
knowledge-ops-agent/
├── app.py                     # Streamlit 演示入口
├── AGENTS.md                  # Agent 入口路由器（操作手册）
├── PROGRESS.md                # 项目进度看板
├── DECISIONS.md               # 架构决策记录
├── README.md / README_CN.md   # 精简入口（中英双语）
├── documents/                 # 文档语料（本体系，见 documents/README.md）
├── data/
│   ├── kb_docs/               # 知识库 markdown 源文档
│   ├── tickets.json           # 工单数据
│   ├── eval_set.csv           # 离线评估集
│   ├── index/                 # FAISS 索引产物
│   └── eval_results/          # 评估输出（gitignore）
├── src/
│   ├── agents/                # main_agent + retrieval_agent + guardrails
│   ├── api/                   # FastAPI 服务（/healthz + /agent/ask）
│   ├── evals/                 # run_evals / metrics / error_analysis / external_bench
│   ├── rag/                   # chunking / build_index / retrieve / hybrid
│   ├── repositories/          # TicketRepository / KBRepository（线程安全单例）
│   ├── tools/                 # kb_search / ticket_tools / escalation_tools
│   └── utils/                 # config / logging / resilience（熔断+缓存）
└── tests/                     # 单测（pytest）
```

## 十一、已知限制

当前版本仍然有这些真实限制：

- escalation 路由和工具选择仍可能受 phrasing 影响，尤其是在"升级政策说明"和"具体 case 的升级建议"之间
- evidence 质量依赖 retrieval 质量 and normalization 质量；`retrieval_agent` 提高了 KB evidence 一致性，但不能保证检索相关性永远完美
- 第三方 OpenAI-compatible provider 的结构化输出仍可能波动，因此代码里除了 prompt 约束，还有 fallback parsing 和 post-processing（`_coerce_agent_output`）
- 对非常短或非常模糊的用户输入，`kb`、`clarify` 和 `escalation` 的边界仍可能承压
- 当前系统是一个 lightweight agent workflow，不是 production-ready multi-agent platform。`retrieval_agent` 是 evidence layer，不是 fully autonomous planner
- 离线评测是行为导向、规则化的，它适合帮助迭代，但不能替代真实生产监控或人工 review
- 本地 ticket 和 KB 数据都是 demo 资产，不是真实生产支持数据
- 多实例限流需 Redis（当前单实例内存限流）

## 十二、后续方向

当前架构下合理的下一步，应该是渐进式改进，而不是平台化大跃进：

- **提升 retrieval ranking 和 reranking**：更好的排序有助于短 KB 问题，也能减少回答前的弱相关 evidence
- **提高 escalation routing 稳定性**：escalation case 仍然会受到措辞影响，尤其在"政策说明"和"个案升级建议"的边界上
- **继续加强 evidence normalization**：下一步可以让 KB 和 escalation 的 evidence 格式更稳定
- **扩展离线 eval 覆盖面**：更丰富的 eval set 和更有针对性的 regression case，有助于更早发现 route、tool 和 evidence 回归
- **为 escalation 增加可选的人在回路审批**：escalation 很适合在真正下游动作前，先加一层轻量 review / approval
- **继续收紧 refusal 和 clarification 边界**：更多 edge-case 覆盖会让系统在模糊或不安全 phrasing 下更稳
- **对接真实 KB 和 ticket backend**：如果项目从本地 demo 继续往前走，最实际的一步是替换掉本地 demo 文件，接上真实内部系统

## 参考

- [工具契约](tools.md)
- [评测体系](evaluation.md)
- [人工验收清单](manual-review-checklist.md)
- [演示场景](04-reports/demo-scenarios.md)
- [决策记录](../../DECISIONS.md)
