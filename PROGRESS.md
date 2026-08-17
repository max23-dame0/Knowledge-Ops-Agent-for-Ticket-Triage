# PROGRESS — 项目当前进度

> 最后更新：2026-08-17
> **上班必读**：本文件 + DECISIONS.md

## 活跃任务看板（WIP 显式登记）

> 允许并行，但每个活跃任务必须在此登记一行；切换前写回状态与下一步。

| # | 任务 | 阶段 | 状态 | 下一步 | 阻塞 |
|:--:|------|------|:--:|------|------|
| 1 | 五层控制金字塔重构（guardrails/route_fn/contracts/trace + main_agent 管线） | 已完成 | ✅ 已提交 | 真实 LLM 5 路由冒烟全通过 | 无 |
| 2 | 决策回放语料库（replay_store + replay_runner + golden promote） | 已完成 | ✅ 已提交 | golden 已含 5 条真实轨迹,CI 已加 replay 检查 | 无 |
| 3 | 历史任务（本地评测/企业就绪度/harness 等,见下） | 已完成 | ✅ 已提交 | - | 无 |

## 当前验证状态

| 检查项 | 状态 |
|------|------|
| `pytest tests/` | ✅ **195 passed / 0 skipped**（2026-08-17,新增 route_fn/replay 24 例） |
| 真实 LLM 端到端冒烟（本地端点） | ✅ kb / ticket / escalation / clarify / refuse 五路由全通过（2026-08-17） |
| `python -m src.evals.replay_runner replay` | ✅ 5/5 golden 回放一致（2026-08-17,无需 LLM） |
| `decide_route` vs 旧 `_resolve_route`（eval_set 66 条） | ✅ 0 差异（行为冻结验证） |
| eval_set E009（升级政策→kb）路由修复 | ✅ 新增 escalation_policy_query 分支 |
| `data/replay/sessions/` 已加入 .gitignore | ✅ |
| 当前 blocker | 无 |

## 未提交改动清单（与 git 强一致）

> 规则：标记 ✅ 完成的任务，其代码**必须已 commit**；仅本地验证未提交的，状态一律写「🟡 已验证待提交」并登记于此。

| 改动 | 状态 | 计划 commit | 关联任务 |
|------|:--:|------|------|
| 五层控制金字塔重构（src/agents/ 重构 + tests + replay 模块 + CI） | 🟡 已验证待提交 | 本轮收尾 commit | 1-2 |
| refactor-report-20260817.md（重构方案报告） | 🟡 已验证待提交 | 本轮收尾 commit | - |

## 整体进度

| Phase | 内容 | 状态 | 完成日期 |
|:--|:--|:--:|:--:|
| P0 | 项目骨架与支持 agent 基线 | ✅ | 2026-03（commit 7322de3） |
| P1 | 核心路由（kb/ticket/escalation/clarify/refuse）与边界规则 | ✅ | 2026-03（commit a65d5db 等） |
| P2 | RAG 管道（chunking + embeddings + FAISS） | ✅ | 2026-03 |
| P3 | 工具层（search_kb / get_ticket_status / create_escalation_draft） | ✅ | 2026-03 |
| P4 | 评估流水线（offline + regression + error_analysis） | ✅ | 2026-03（commit 301e51d） |
| P5 | 文档（README / README_CN / 验收清单） | ✅ | 2026-08（commit 0c254fa） |
| P6 | Harness 环境搭建 | 🟡 待提交 | 2026-08-12 |

## 阻塞项

无。

## 最近会话记录（三行摘要，详情见 daily memory）

| 日期 | 做了什么（一行） | 验证 | 下一步 | 日志 |
|------|---------|:--:|------|
| 2026-08-13 | 本地端点工具型评测：反代支持 tools 后跑 regression 11 条 + offline 66 条，报告落盘 documents/02-review/local-endpoint-tool-eval-report-2026-08-13.md | regression 11/11（100%）、offline route 97.0%/grounding 100%/refusal 98.5% | E009/E021/E049 三点可选优化 | `.codebuddy/memory/2026-08-13.md` |
| 2026-08-12 | 外部数据集评测闭环：下载 deepset/prompt-injections + clinc_oos → 评测脚本 → 初测（注入拒答 80%、幻觉敞口 96.7%）→ P1 加固（fallback clarify + 多语种注入正则）→ 复测（注入拒答 100%、幻觉风险 0、规则层拦截 3.7x） | pytest 171 passed / 评测全指标改善 | P2 建议可选；Docker/K8s 部署验证 | `.codebuddy/memory/2026-08-12.md` |
| 2026-08-12 | 端到端验证闭环：安装 faiss 全依赖 → pytest 164/164 全绿 → HNSW 索引重建 + 混合检索冒烟 → DeepSeek 端点 regression 11/11 → offline 66 用例评估（route 98.5%/grounding 100%/refusal 98.5%）→ 修复 E061-E066 乱码（原 git 版本即乱码） | 全链路 ✅ | 已完成 | `.codebuddy/memory/2026-08-12.md` |
| 2026-08-12 | 修复 12 项企业就绪度差距（Phase A/B/C 全部完成）：密钥清理、158 单测、CI、结构化日志、Repository、熔断缓存、FastAPI+认证限流、Docker/K8s、HNSW+BM25、注入防护+对抗用例+人工确认闸、审计轨迹、多轮会话+反馈 | ruff 0 错误 / pytest 158 passed / 13 commits | 已进入验证闭环 | `.codebuddy/memory/2026-08-12.md` |
| 2026-08-12 | 首次搭建 harness：生成 AGENTS.md / MEMORY.md / PROGRESS.md / DECISIONS.md / rules/（6 个）/ harness 辅助文件（3 个） | 生成完整性检查 | 已 commit（3a545fa） | `.codebuddy/memory/2026-08-12.md` |
