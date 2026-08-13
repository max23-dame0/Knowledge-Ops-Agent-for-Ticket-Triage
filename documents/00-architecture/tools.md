---
doc_id: ARCH-002
title: "工具契约"
category: "architecture"
role: "[State]"
status: "published"
date: "2026-08-13"
author: "knowledge-ops-agent 团队"
tags: ["tools", "kb-search", "ticket", "escalation", "contract"]
related:
  - "architecture.md"
---

# 工具契约

> **摘要**：主 Agent 当前使用的三个本地 function tool 的输入输出契约与典型场景。
> **来源**：由原 README 拆分迁移（2026-08-13 文档治理），与 `src/tools/` 代码保持一致。

## 目录

- [一、search_kb(query)](#一search_kbquery)
- [二、get_ticket_status(ticket_id)](#二get_ticket_statusticket_id)
- [三、create_escalation_draft(issue_summary, evidence)](#三create_escalation_draftissue_summary-evidence)

---

## 一、search_kb(query)

**用途**：从本地知识库中检索可用于 grounding 的段落。

**典型场景**：

- VPN 登录问题
- 密码重置
- 邮箱验证
- 计费与退款
- 发票与权限问题

**返回**：

```text
query
results
  - source_title
  - passage
  - score
```

## 二、get_ticket_status(ticket_id)

**用途**：读取本地工单数据并返回稳定的结构化记录。

**典型场景**：

- 当前状态
- 负责人
- 优先级
- 最后更新时间
- 摘要
- 分类

**返回**：

```text
ticket_id
found
error
ticket
```

## 三、create_escalation_draft(issue_summary, evidence)

**用途**：基于问题摘要和证据生成简单升级建议草稿。

**典型场景**：

- 这个问题要不要升级？
- 应该转给哪个团队？
- 严重程度如何？

**返回**：

```text
severity
suggested_team
escalation_summary
recommended_next_step
```

## 参考

- [架构说明](architecture.md)
- [演示场景](04-reports/demo-scenarios.md)
