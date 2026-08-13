---
doc_id: ARCH-003
title: "评测体系"
category: "architecture"
role: "[State]"
status: "published"
date: "2026-08-13"
author: "knowledge-ops-agent 团队"
tags: ["evaluation", "offline-eval", "regression", "metrics", "benchmark"]
related:
  - "architecture.md"
  - "04-reports/demo-scenarios.md"
  - "02-review/external-benchmark-total-report-2026-08-13.md"
---

# 评测体系

> **摘要**：本项目离线评估的权威说明——数据集、规则式指标、runner、错误分析、常用命令与外部评测。
> **来源**：由原 README 拆分迁移（2026-08-13 文档治理），与 `src/evals/` 代码保持一致。

## 目录

- [一、评测定位](#一评测定位)
- [二、Eval 数据集](#二eval-数据集)
- [三、当前主要评什么](#三当前主要评什么)
- [四、Eval runner](#四eval-runner)
- [五、Grounding / evidence 的理解方式](#五grounding--evidence-的理解方式)
- [六、错误分析](#六错误分析)
- [七、常用命令](#七常用命令)
- [八、外部评测](#八外部评测)

---

## 一、评测定位

当前项目使用的是一套轻量离线评测流程，用来衡量行为质量，而不是 benchmark 式模型性能分数。

评测的目标很实际：确认 Agent 是否能正确路由、用对工具、在该澄清时澄清、在该拒答时拒答，以及在需要 grounding 的路径上返回 evidence。

> **重要说明**：当前评测是轻量、规则化的，还没有引入 semantic grader 或 LLM judge（DECISIONS.md D005）。结果适合用于迭代、回归检查和 demo 调试，不应被包装成强 benchmark 成绩。

## 二、Eval 数据集

文件：`data/eval_set.csv`

当前字段：

```text
id
question
expected_route
should_clarify
should_use_tool
expected_tool
expected_behavior
gold_facts
unsafe
```

覆盖的 route：`kb`、`ticket`、`escalation`、`clarify`、`refuse`

## 三、当前主要评什么

离线 eval 当前主要关注五类行为指标：

| 指标 | 检查点 |
|------|--------|
| `route_accuracy` | 系统是否选择了预期 route：`kb`、`ticket`、`escalation`、`clarify`、`refuse` |
| `tool_use_accuracy` | 是否调用了预期工具，或者在不该调用工具时正确保持不用 |
| `clarification_accuracy` | 信息不足的请求是否真的被澄清，而不是被猜测回答 |
| `grounding_presence` | 在应当 grounding 的路径上是否返回了 evidence |
| `refusal_accuracy` | 明显不安全请求是否被拒答 |

这套设计与当前系统形态一致：一个负责 route 和 tool decision 的 `main_agent`，再加一个帮助稳定 KB evidence 的轻量 `retrieval_agent`，而不是单独的 planning agent。

## 四、Eval runner

文件：`src/evals/run_evals.py`

功能：

- 读取 CSV 评测集
- 逐条运行主 Agent
- 收集归一化后的结构化输出
- 计算轻量规则化指标
- 单条失败不会中断整批评测
- 将逐条结果保存到 `data/eval_results/`（gitignore 排除）

除了完整 offline run，runner 还支持一个小型 **regression 模式**（`--mode regression`），用于本地快速检查关键场景。

逐条结果文件当前会保存：`id`、`question`、`expected_route`、`predicted_route`、`should_clarify`、`predicted_clarify`、`expected_tool`、`predicted_tool`、`unsafe`、`refused`、`evidence_expected`、`evidence_present`、`route_ok`、`tool_ok`、`clarify_ok`、`grounding_ok`、`refusal_ok`、`pass_fail_summary`、`error`

## 五、Grounding / evidence 的理解方式

这里对 grounding 的判断是刻意收敛、偏实用的：

- 对 `kb`、`ticket`、`escalation`，输出应当包含 evidence 或来源信息
- 对 `clarify` 和 `refuse`，evidence 可以为空，不按同样标准处理

`retrieval_agent` 的加入也正是为了这件事：它的目的，是让 KB evidence 更稳定、更容易被检查，而不是引入一个新的自治推理环。

## 六、错误分析

文件：`src/evals/error_analysis.py`

当前汇总的错误类型包括：

- route 错误
- 工具误调用
- 漏澄清
- 漏拒答
- evidence 缺失

## 七、常用命令

运行离线评测：

```bash
.venv\Scripts\python.exe -m src.evals.run_evals --mode offline
```

运行 regression smoke checks：

```bash
.venv\Scripts\python.exe -m src.evals.run_evals --mode regression
```

运行错误分析：

```bash
.venv\Scripts\python.exe -m src.evals.error_analysis
```

## 八、外部评测

`src/evals/external_bench.py` 支持基于外部公开数据集的对抗评测（可重复跑）：

- deepset/prompt-injections（注入样本）
- clinc_oos（OOS 域外样本）

数据下载到 `data/eval_datasets`（gitignore）。初测发现注入拒答 80%、幻觉敞口 96.7% → P1 加固（fallback kb→clarify + 多语种注入检测）→ 复测注入拒答 100%、幻觉风险 0。最新汇总报告见 `02-review/external-benchmark-total-report-2026-08-13.md`。

## 参考

- [架构说明](architecture.md)
- [外部评测汇总报告](../02-review/external-benchmark-total-report-2026-08-13.md)
- [本地端点工具型评测报告](../02-review/local-endpoint-tool-eval-report-2026-08-13.md)
