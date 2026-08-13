---
doc_id: DOC-001
title: "文档索引"
category: "reference"
role: "[State]"
status: "published"
date: "2026-08-13"
author: "knowledge-ops-agent 团队"
tags: ["index", "documentation", "navigation"]
related:
  - "../README_CN.md"
  - "../DECISIONS.md"
---

# 文档索引

> **摘要**：本项目 `documents/` 语料的统一索引入口（Agent 检索起点）。新增 / 修改文档后必须同步本索引。
> **约定**：语料文档均需 frontmatter（`doc_id` / `title` / `category` / `role` / `status` / `date` / `author`）；`[State]` 修改即更新，`[Delta]` 只增不改，`[Cold]` 仅参考。

## 场景查找表

| 我想... | 先看这个 | 再看这个 |
|--------|---------|---------|
| 快速了解项目怎么跑 | 根目录 `README_CN.md`（中文）/ `README.md`（英文） | [架构说明](00-architecture/architecture.md) |
| 理解架构、路由与各模块职责 | [架构说明](00-architecture/architecture.md) | [决策记录](../DECISIONS.md) |
| 查三个工具的入参出参 | [工具契约](00-architecture/tools.md) | `src/tools/` |
| 了解评测方法与命令 | [评测体系](00-architecture/evaluation.md) | [02-review](02-review/) 报告 |
| 准备 demo / 面试演示 | [演示场景指南](04-reports/demo-scenarios.md) | [人工验收清单](00-architecture/manual-review-checklist.md) |
| 验收部署后的 UI 冒烟 | [人工验收清单](00-architecture/manual-review-checklist.md) | [演示场景指南](04-reports/demo-scenarios.md) |
| 查最近一次评测结果 | [02-review](02-review/) 最新报告 | [PROGRESS](../PROGRESS.md) |
| 查项目当前进度 | [PROGRESS](../PROGRESS.md) | [决策记录](../DECISIONS.md) |
| 查后续改进规划（自我改进/RAG/评测） | [规划 PLN-001](01-planning/agent-self-improvement-rag-plan-2026-08-13.md) | [决策记录](../DECISIONS.md) |

## 目录结构（带角色标签）

```text
documents/
├── README.md                      ← 本索引（[State] 导航，维护中）
├── 00-architecture/               ← [State] 架构与设计（权威真源，修改即更新）
│   ├── architecture.md            ← 架构说明（定位/路由/模块/限制/方向）
│   ├── tools.md                   ← 工具契约（search_kb / get_ticket_status / create_escalation_draft）
│   ├── evaluation.md              ← 评测体系（数据集/指标/命令/外部评测）
│   └── manual-review-checklist.md ← 人工验收清单（12 条冒烟样本）
├── 01-planning/                   ← [Delta] 规划文档（只增不改）
│   └── agent-self-improvement-rag-plan-2026-08-13.md ← PLN-001 自我改进引擎 + RAG 深化 + 评测升级
├── 02-review/                     ← [Delta] 审查与评测报告（只增不改）
│   ├── enterprise-gap-analysis-2026-08-12.md
│   ├── external-benchmark-report-2026-08-12.md
│   ├── external-benchmark-total-report-2026-08-13.md
│   ├── local-endpoint-tool-eval-report-2026-08-13.md
│   └── ticket-benchmark-cloud-run-guide-2026-08-13.md
└── 04-reports/                    ← [Delta] 项目报告
    └── demo-scenarios.md          ← 演示场景指南（五类路由推荐问题）
```

## 按目录分类索引

| 文档 | 角色 | 日期 | 状态 | doc_id |
|------|:--:|:--:|:--:|:--:|
| [00-architecture/architecture.md](00-architecture/architecture.md) | [State] | 2026-08-13 | published | ARCH-001 |
| [00-architecture/tools.md](00-architecture/tools.md) | [State] | 2026-08-13 | published | ARCH-002 |
| [00-architecture/evaluation.md](00-architecture/evaluation.md) | [State] | 2026-08-13 | published | ARCH-003 |
| [00-architecture/manual-review-checklist.md](00-architecture/manual-review-checklist.md) | [State] | 2026-08-13 | published | ARCH-004 |
| [01-planning/agent-self-improvement-rag-plan-2026-08-13.md](01-planning/agent-self-improvement-rag-plan-2026-08-13.md) | [Delta] | 2026-08-13 | draft | PLN-001 |
| [02-review/enterprise-gap-analysis-2026-08-12.md](02-review/enterprise-gap-analysis-2026-08-12.md) | [Delta] | 2026-08-12 | published | REV-001 |
| [02-review/external-benchmark-report-2026-08-12.md](02-review/external-benchmark-report-2026-08-12.md) | [Delta] | 2026-08-12 | published | REV-002 |
| [02-review/external-benchmark-total-report-2026-08-13.md](02-review/external-benchmark-total-report-2026-08-13.md) | [Delta] | 2026-08-13 | published | REV-003 |
| [02-review/local-endpoint-tool-eval-report-2026-08-13.md](02-review/local-endpoint-tool-eval-report-2026-08-13.md) | [Delta] | 2026-08-13 | published | REV-004 |
| [02-review/ticket-benchmark-cloud-run-guide-2026-08-13.md](02-review/ticket-benchmark-cloud-run-guide-2026-08-13.md) | [Delta] | 2026-08-13 | published | REV-005 |
| [04-reports/demo-scenarios.md](04-reports/demo-scenarios.md) | [Delta] | 2026-08-13 | published | RPT-001 |

## ADR 索引区

> ADR 记录在根目录 [DECISIONS.md](../DECISIONS.md)（D001–D006）。

| ADR | 标题 | 状态 | 日期 |
|-----|------|:--:|:--:|
| D001 | 项目 Harness 体系采用五子系统架构 | 生效 | 2026-08-12 |
| D002 | 规则采用 MDC 风格分层管理 | 生效 | 2026-08-12 |
| D003 | LLM 接入采用 OpenAI 兼容端点 + 可配置模型 | 生效 | 2026-08-12 |
| D004 | 单决策者架构 — main_agent 为唯一顶层决策 owner | 生效 | 2026-08-12 |
| D005 | 评估采用规则式指标（非 LLM judge） | 生效 | 2026-08-12 |
| D006 | OpenAI Agents SDK tracing 运行时关闭 | 生效 | 2026-08-12 |

## 模板索引区

| 模板 | 用途 | 位置 |
|------|------|------|
| 通用文档模板 | 新建语料文档 | `.codebuddy/skills/doc-governance/references/templates/universal-doc-template.md` |
| ADR 模板 | 新增决策记录 | 同上 `adr-template.md` |
| 审计报告模板 | 审查 / 审计报告 | 同上 `audit-report-template.md` |
| 验证报告模板 | 验证 / 测试报告 | 同上 `verification-report-template.md` |

## 维护约定

- 新增语料：先在本文档查重 → 按 §1.2 命名 → 补 frontmatter → 在"按目录分类索引"注册
- 修改 [State] 文档：内容更新后同步更新 `date` / `updated` 字段
- 归档：`status` 改为 `archived` 并移入 `documents/archive/`
- 被替代：保留原位置，frontmatter 标注 `superseded_by`
