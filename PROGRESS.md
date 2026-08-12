# PROGRESS — 项目当前进度

> 最后更新：2026-08-12
> **上班必读**：本文件 + DECISIONS.md

## 活跃任务看板（WIP 显式登记）

> 允许并行，但每个活跃任务必须在此登记一行；切换前写回状态与下一步。

| # | 任务 | 阶段 | 状态 | 下一步 | 阻塞 |
|:--:|------|------|:--:|------|------|
| 1 | Harness 环境首次搭建（AGENTS/MEMORY/PROGRESS/DECISIONS/rules/handoff） | 已生成 | 🟡 已验证待提交 | 人工 review 后 commit（`.codebuddy/` + 4 个根文件） | 无 |
| 2 | 核心功能基线（main_agent + RAG + tools + eval） | 已完成 | ✅ 已提交（git log: 0c254fa 及之前） | 无 | 无 |

## 当前验证状态

| 检查项 | 状态 |
|------|------|
| `.venv\Scripts\python.exe -m src.rag.build_index` | ⬜ 未在本会话验证（基线已建索引：`data/index/`） |
| `... run_evals --mode regression`（基线：11 个用例，需 LLM 环境） | ⬜ 未在本会话验证（需 `.env` + 模型端点） |
| lint 检查 | ⬜ 未运行（`py_compile` 可作最低检查） |
| git status / 未提交清单 | 🟡 未提交：`.codebuddy/` 全部 + AGENTS.md/PROGRESS.md/DECISIONS.md |
| 当前 blocker | 无 |

## 未提交改动清单（与 git 强一致）

> 规则：标记 ✅ 完成的任务，其代码**必须已 commit**；仅本地验证未提交的，状态一律写「🟡 已验证待提交」并登记于此。

| 改动 | 状态 | 计划 commit | 关联任务 |
|------|:--:|------|------|
| Harness 文件（AGENTS.md / PROGRESS.md / DECISIONS.md / .codebuddy/） | 🟡 已生成待提交 | 人工 review 后单次 commit | 1 |

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
| 2026-08-12 | 首次搭建 harness：扫描项目（Python + openai-agents + Streamlit + FAISS），生成 AGENTS.md / MEMORY.md / PROGRESS.md / DECISIONS.md / rules/（6 个）/ harness 辅助文件（3 个） | 生成完整性检查 | 人工 review 后 commit | `.codebuddy/memory/2026-08-12.md` |
