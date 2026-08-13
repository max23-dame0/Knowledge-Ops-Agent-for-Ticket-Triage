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

## D007: LLM judge 仅评质量维度，不替代行为判定指标

- **日期**：2026-08-13（PLN-001 D 线，对 D005 的修正性补充）
- **决策**：引入 semantic grader（D1）作为**补充性质量评测**，仅对 kb 路由样本的最终回答做三维评分（正确性/完整性/证据支撑，1-5 分）；route/tool/clarify/refusal/grounding 五项行为指标继续由规则式 metrics（D005）判定，judge 无权改变行为判定结果
- **原因**：自我改进闭环（A5 门控）需要回答质量的量化信号，但 LLM judge 不稳定、成本高，不能动摇 D005 的确定性回归基线
- **否决方案**：用 judge 完全替代规则指标（回归基线漂移、成本不可控）；或完全不用 judge（质量维度盲区，A5 门控只有行为信号）
- **回退/可逆方案**：judge 作为独立模块（`src/evals/semantic_grader.py`），不接入 run_evals 主流程；关闭开关即回到纯规则基线；D2 校准一致性 <85% 时不启用 judge 参与门控
- **约束**：judge 只在抽样/门控场景调用，不进常规回归；judge 打分不写入行为指标 CSV 的判定列

## D008: Embedding 采用 OpenAI 兼容 API 通道 + 本地模型兜底

- **日期**：2026-08-13
- **决策**：embedding 统一走 `src/rag/embedding.py` 的 `EmbeddingClient` 接口。配置 `EMBEDDING_API_KEY`（+ `EMBEDDING_BASE_URL`/`EMBEDDING_MODEL_ID`）时走 OpenAI 兼容 `/v1/embeddings` 远程 API（当前 SiliconFlow `Qwen/Qwen3-VL-Embedding-8B`，4096 维，API 返回向量做 L2 归一化对齐 sentence-transformers 语义）；未配置 key 时回退本地 `all-MiniLM-L6-v2`。构建索引与检索共用同一接口，`kb_metadata.json` 记录实际 `model_name`
- **原因**：摆脱本地下载/加载 embedding 模型的重量级依赖与磁盘占用，且 bge-m3 多语言检索质量优于 MiniLM；符合 D003 的 OpenAI 兼容通道原则
- **否决方案**：替换为专用 SDK 调用（破坏 OpenAI 兼容通道）；或在 rag 层散落多份模型配置（违反集中管理）
- **回退/可逆方案**：删除 `.env` 中 `EMBEDDING_API_KEY` 即自动回退本地模型（**回退后必须用本地模型重建索引**，否则 1024 维索引与 384 维 query 不匹配会报错）；索引重建入口不变（`python -m src.rag.build_index`）
- **约束**：embedding key/url 只存 `.env`；切换 embedding 模型后必须重建 `data/index/` 再跑 regression 验证 KB 路径
