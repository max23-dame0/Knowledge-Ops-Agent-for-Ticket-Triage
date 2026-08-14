---
doc_id: "REP-D2-001"
title: "D2 judge 校准报告：semantic grader 与人工标注一致性"
category: "review"
date: "2026-08-14"
status: "delivered"
related:
  - "pln001-final-report-2026-08-13.md"
  - "../01-planning/agent-self-improvement-rag-plan-2026-08-13.md"
---

# D2 judge 校准报告（2026-08-14）

## 结论

**judge 当前不启用**（严格一致率 66.7% < 85% 阈值，ADR D007 + M4 约束正确执行）。

| 口径 | 一致率 | 阈值 | 判定 |
|------|:--:|:--:|:--:|
| 严格（|judge−human|=0） | **66.7%**（24/36 维度） | ≥85% | ❌ 未达标 |
| 宽松（|judge−human|≤1） | **88.9%**（32/36 维度） | — | 达标（参考） |

## 方法

- 样本：offline eval 集前 12 条 kb 样本（E001-E012）
- 流程：真实 agent 回答 → SemanticGrader 打分 → 用户人工标注（1-5 分三维）
- 标注文件：`data/judge_calibration_labeling.tsv`（已修复 Excel 保存造成的列错位，经用户确认）

## 维度级分析

| 维度 | 严格一致 | 宽松一致 | 特征 |
|------|:--:|:--:|------|
| correctness 正确性 | **12/12（100%）** | 12/12 | judge 完全可靠 |
| completeness 完整性 | 5/12（41.7%） | **12/12（100%）** | 全是 ±1 分歧，judge 系统性保守（7 条中 6 条 judge=4 而人工=5） |
| evidence_support 证据支撑 | 7/12（58.3%） | 8/12（66.7%） | 存在大分歧（E005 diff=3、E003/E007/E012 diff=2），judge 低评而人工高评 |

## 根因：judge 在 evidence_support 维度是"盲评"

`SemanticGrader.grade()` 只把 `question` 和 `answer` 传给 judge，**未附带 evidence 字段**。judge 看不到检索证据，只能凭 answer 文本猜测证据支撑度：

- **E005**（judge=2 vs 人工=5）：answer 含"知识库明确支持更正抬头流程"，但 judge 未见到 `evidence` 里对 invoice_request 文档的引用，低估了支撑度
- **E007**（judge=2 vs 人工=4）、**E012**（judge=5 vs 人工=3）同源

correctness/completeness 两个纯文本维度不受影响（100%/100% 宽松一致），佐证该归因。

## 结论与后续动作

1. **judge 暂不启用**：门控（A5）继续只用规则式指标 + 安全快照，符合 D007"校准 <85% 不启用"的约束
2. **修复 judge 输入**（下一步）：`grade()` 增加 `evidence: list[str]` 参数，把 agent 输出的 evidence 传入 prompt，让 evidence_support 维度有据可评
3. **修复后重新校准**：同 12 样本重跑 judge（或重新抽样），预期 evidence_support 一致率显著提升；达标后再评估启用

## 变更文件

| 文件 | 说明 |
|------|------|
| `data/judge_calibration_labeling.tsv` | 12 条 kb 样本 + judge 分 + 人工标注（列错位已修复，经用户确认） |
| `src/evals/judge_calibration.py` | 报告命令（commit aac5fab） |
| `documents/02-review/d2-judge-calibration-report-2026-08-14.md` | 本报告 |

## 复现命令

```bash
.venv\Scripts\python.exe -m src.evals.judge_calibration --report   # 一致率（严格+宽松）
```
