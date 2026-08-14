---
description: src/evals 评估流水线规则
globs: "**/evals/**"
alwaysApply: false
---
# evals 层规则

> 本规则适用于 `**/evals/**` 匹配的文件（run_evals.py / metrics.py / error_analysis.py）。
> 生效模式：涉及评估时加载

---

## 核心约束

1. **regression 用例是回归防线**：`REGRESSION_CASES` 的 11 个用例（5 类路由全覆盖）不得随意删减，新增路由行为时必须同步补用例。why：这是本项目唯一的自动化回归手段；when：改路由/工具行为时；when_remove：引入更强回归框架时。
2. **评估是规则式**：指标实现（route_accuracy / tool_use_accuracy / clarification_accuracy / grounding_presence / refusal_accuracy）保持纯函数、无 LLM judge 依赖。why：决策 D005；when：加新指标时；when_remove：D005 变更时。
3. **单样本失败不中断全跑**：run_evals 必须容忍单个样本异常（记录 error 字段继续）。why：第三方提供商偶发 429/超时；when：改 runner 时；when_remove：永不。
4. **429 必须重试退避**：`_run_agent_with_retry`（重试 3 次、指数退避）不得移除。why：MiniMax 端点有 rate limit（tech-traps）；when：改 agent 调用时；when_remove：供应商去掉限流时。
5. **产物纪律**：评估输出只写 `data/eval_results/`（gitignore 排除），禁止写回 `data/eval_set.csv` 或仓库其他位置。why：评估产物是临时数据；when：任何输出；when_remove：永不。

## 代码风格

- 指标函数输入输出用纯数据（dict/float/bool），不依赖全局状态
- CSV 读写用 csv/pandas 标准库，文件编码 utf-8-sig（兼容 Excel）
- 用例命名 `route_场景`（如 `ticket_compact`、`refuse_prompt`）

## 禁止模式

- 在 metrics.py 中 import agents 层逻辑做判断（指标只吃输入 dict）
- 硬编码绝对路径（`DEFAULT_EVAL_PATH` 等常量用相对路径 + 常量）
- 把 LLM 输出直接当 ground truth

## 推荐模式

- 新增行为维度时：eval_set.csv 加列 + metrics.py 加指标 + REGRESSION_CASES 加用例，三处同步
- 评估结果解读先看 error_analysis 的类别计数，再定位具体样本
