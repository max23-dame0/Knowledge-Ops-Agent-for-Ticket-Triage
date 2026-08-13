# DECISIONS — 架构决策记录

> 记录关键设计决策及原因。**上班必读**，避免新会话推翻已有决定。
> 格式：日期 + 决策 + 原因 + 否决方案 + **回退/可逆方案** + 约束条件（L05 标准）
> 强调「可逆设计」：每条决策须写明若上线出问题如何回退，避免不可逆改动。

---

## D001: 项目 Harness 体系采用五子系统架构

- **日期**：2026-08-12
- **决策**：采用 Harness Engineering 五子系统模型（指令+工具+环境+状态+反馈），通过入口文件（AGENTS.md）/PROGRESS.md/MEMORY.md/DECISIONS.md 四个核心文件 + 分层规则（`.codebuddy/rules/`）建立 coding agent 工作环境
- **原因**：结构化的 harness 保证跨会话连续性、上下文可控（渐进式披露）、决策不被推翻
- **否决方案**：纯 Prompt 驱动（无结构化 harness 文件，上下文效率低、跨会话无法连续性）
- **回退/可逆方案**：harness 文件均为 Markdown，可随时 `git revert` 回退；某规则误伤开发时删对应行即可
- **约束**：所有 Agent 会话必须遵守入口文件中的上班/下班/WIP 显式登记流程

## D002: 规则采用 MDC 风格分层管理

- **日期**：2026-08-12
- **决策**：项目规则按作用域（global → 模块）分层管理，每个规则文件使用 YAML frontmatter 声明生效条件（globs / alwaysApply）
- **原因**：避免一次性全量加载所有规则导致上下文溢出，按模块（agents/evals/rag/tools/utils）差异化约束
- **否决方案**：所有规则写入单文件（上下文预算不可控，冲突难以解决）
- **回退/可逆方案**：规则均为独立 md 文件，可按需删除/合并
- **约束**：规则文件 < 80 行，入口文件 < 200 行，MEMORY.md < 200 行

## D003: LLM 接入采用 OpenAI 兼容端点 + 可配置模型

- **日期**：2026-08-12（来源：`documents/00-architecture/architecture.md` + `.env.example` 归纳）
- **决策**：通过 `OpenAIChatCompletionsModel` 调用第三方 OpenAI 兼容端点（当前 MiniMax M2.7，`LLM_BASE_URL`/`LLM_MODEL_ID`/`LLM_API_KEY` 全部走 `.env`）
- **原因**：README 明确运行时期望 OpenAI 兼容 chat-completions 接口；模型/端点可配置便于切换供应商
- **否决方案**：硬编码官方 OpenAI SDK 专用调用（无法兼容第三方提供商）
- **回退/可逆方案**：改 `.env` 即可切换模型，无代码改动
- **约束**：代码中不得出现硬编码 key/URL；密钥只存 `.env`

## D004: 单决策者架构 — main_agent 为唯一顶层决策 owner

- **日期**：2026-08-12（来源：`documents/00-architecture/architecture.md` 归纳）
- **决策**：`main_agent` 拥有路由（kb/ticket/escalation/clarify/refuse）、澄清、拒答、工具选择的全部顶层决策权；`retrieval_agent` 仅为 KB 证据规范化层，不参与路由
- **原因**：本项目定位"单决策 agent + 受控子模块"，不是自由多 agent 交接系统；保证行为可检视、可评估
- **否决方案**：多 agent 自由交接架构（复杂、难调试、评估不稳定）
- **回退/可逆方案**：架构调整时保留 `retrieval_agent` 接口兼容，可随时在 main_agent 内换实现
- **约束**：不得在 agents 层之外做路由决策；工具输出必须经 `_finalize_response` 规范化

## D005: 评估采用规则式指标（非 LLM judge）

- **日期**：2026-08-12（来源：`documents/00-architecture/evaluation.md` 归纳）
- **决策**：离线评估用轻量规则指标（route_accuracy / tool_use_accuracy / clarification_accuracy / grounding_presence / refusal_accuracy），不做语义打分
- **原因**：项目是行为评估（路由/工具/澄清/拒答/证据），规则式足以支撑回归与迭代，成本低且稳定
- **否决方案**：LLM judge 语义评分（成本高、不稳定，demo 阶段收益低）
- **回退/可逆方案**：评估管线独立（run_evals/metrics 模块），后续可加 judge 而不动 agent
- **约束**：结果不宣称为 benchmark 级结论；`data/eval_results/` 产物不入库

## D006: OpenAI Agents SDK tracing 运行时关闭

- **日期**：2026-08-12（来源：`documents/00-architecture/architecture.md` §九 归纳）
- **决策**：`RunConfig(tracing_disabled=True)`，运行时不启用 SDK tracing，改用项目自带 `src/utils/logging.py` 的 `key=value` 日志
- **原因**：兼容非 OpenAI 提供商；自带日志已覆盖 user_input/route_hints/tool_calls/response_summary 全链路
- **否决方案**：依赖 SDK tracing（第三方提供商下不稳定）
- **回退/可逆方案**：tracing 开关是配置项，随时可恢复
- **约束**：新增关键流程时同步补日志，保持可观测性
