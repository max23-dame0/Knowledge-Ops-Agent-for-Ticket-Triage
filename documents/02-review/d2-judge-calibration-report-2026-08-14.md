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

## 最终结论

**judge 不启用**。两轮校准（盲评 + 证据感知）均未达 85% 阈值，D007 约束正确执行，门控继续只用规则式指标 + 安全快照。D 线就此收敛：D1 实现完成，D2 校准完成且如实判定"不可用"，不再通过反复调 prompt 追逐阈值（防校准集过拟合）。

## 两轮校准对比

| 轮次 | 严格一致率 | 宽松一致率 | 判定 |
|------|:--:|:--:|:--:|
| 第 1 轮：盲评（judge 仅见 question+answer） | 66.7%（24/36） | 88.9%（32/36） | ❌ |
| 第 2 轮：证据感知（judge 见 question+answer+evidence） | **50.0%**（18/36） | **75.0%**（27/36） | ❌ 更差 |

## 方法

- 样本：offline eval 集前 12 条 kb 样本（E001-E012），两轮沿用同一批人工标注（标注文件已修复 Excel 列错位并经用户确认；重跑时 `build_labeling_sheet` 自动保留人工标注）
- 流程：真实 agent 回答 → SemanticGrader 打分 → 与人工标注比对

## 第 1 轮维度分析（盲评）

| 维度 | 严格 | 特征 |
|------|:--:|------|
| correctness | 12/12（100%） | 完全可靠 |
| completeness | 5/12（宽松 12/12） | judge 系统性保守（judge=4 vs 人工=5） |
| evidence_support | 7/12 | 大分歧，judge 低评人工高评 |

根因假设：judge 看不到 evidence，evidence_support 是盲评 → 修复 `grade()` 传 evidence（commit bfacaf2）。

## 第 2 轮维度分析（证据感知）

| 维度 | 严格 | 关键分歧 |
|------|:--:|------|
| correctness | 10/12 | E008 diff=2（退化） |
| completeness | 3/12 | E007 diff=2、E008 diff=3 |
| evidence_support | 5/12 | E003 diff=4（judge=5 vs 人工=1）、E008 diff=4（judge=1 vs 人工=5） |

## 修复未生效的根因：judge 与人工的评分标准结构性不一致

1. **E003**（注册收不到验证邮件）：agent 的 evidence 是邮箱验证文档的 3 条检索命中，judge 认为"有证据"打 5 分；人工判 1 分——人工的标准是 **answer 文本是否真正复用了证据内容**（该 answer 只是"可按指引排查"的空泛复述，未引用具体步骤），而非"证据列表是否存在"。
2. **E008**（P1 响应时限）：answer 简洁准确（30 分钟），evidence 3 条高分命中，人工打全 5；judge 反打 3/2/1——judge 被证据原文的 markdown 标题/无关第二条命中干扰，且对"简洁答案"系统性低估。
3. correctness/completeness 同步退化：judge 看到证据后整体评分行为漂移（第三方端点非确定性 + 对证据噪声敏感）。

结论：分歧不是"judge 缺信息"，而是 **judge 与人工对三个维度的操作化定义不一致**（尤其 evidence_support："有证据列表" vs "回答体现证据"）。这属于评分标准工程问题，不是传参能修复的。

## 决策与后续动作

1. **judge 不启用**（D007 约束内）：门控只用规则式指标 + 安全快照，行为判定不受影响
2. **不再追调 prompt 刷阈值**：连续调 prompt 是校准集过拟合，违背防 reward hacking 精神
3. **若未来要启用 judge**（可选，不阻塞）：
   - 需先与标注者对齐三维操作化定义（写评分 rubric，含正反例）
   - evidence_support 改判"answer 是否复用了 evidence 内容"（可让 judge 输出引用 span 佐证）
   - 用独立校准集验证（不与调 prompt 用同一批样本）
4. **D 线状态**：D1 ✅ 实现、D2 ✅ 校准（判定不启用）、D3 挂起等方向 B —— PLN-001 D 线按计划收敛

## 变更文件

| 文件 | 说明 |
|------|------|
| `data/judge_calibration_labeling.tsv` | 12 样本 + judge 分（证据感知版）+ 人工标注 |
| `src/evals/semantic_grader.py` | grade() 支持 evidence 参数（commit bfacaf2） |
| `src/evals/judge_calibration.py` | 重跑保留人工标注 + 报告命令 |
| 本报告 | 两轮校准对比与根因分析 |

## 复现命令

```bash
.venv\Scripts\python.exe -m src.evals.judge_calibration --report   # 一致率（严格+宽松）
```
