# 企业工单评测报告

生成时间：2026-08-14 09:13:17 UTC

数据集：Tobi-Bueck 客服工单（18537）+ alezzandro/itsm_tickets（900）

评测模型：deepseek-v4-flash-202605

## Tobi 有监督分类（官方 GT）

### type（4 类）

| 模型 | accuracy | vs 多数类基线 | vs 随机 |
|---|---|---|---|
| 多数类基线 | 0.4010 | — | +0.1510 |
| 随机基线 | 0.2500 | -0.1510 | — |
| deepseek-v4-flash-202605 | 0.7143 | +0.3133 | +0.4643 |

### priority（3 类）

| 模型 | accuracy | vs 多数类基线 | vs 随机 |
|---|---|---|---|
| 多数类基线 | 0.4074 | — | +0.0741 |
| 随机基线 | 0.3333 | -0.0741 | — |
| deepseek-v4-flash-202605 | 0.3750 | -0.0324 | +0.0417 |

### queue（10 类）

| 模型 | accuracy | vs 多数类基线 | vs 随机 |
|---|---|---|---|
| 多数类基线 | 0.2917 | — | +0.1917 |
| 随机基线 | 0.1000 | -0.1917 | — |
| deepseek-v4-flash-202605 | 0.0000 | -0.2917 | -0.1000 |

## Tobi Agent 行为（无监督）

| 模型 | success_rate | kb_grounding | escalation | answerable | latency_p50 | delta_tok/req |
|---|---|---|---|---|---|---|
| deepseek-v4-flash-202605 | — | — | — | — | — | — |

## ITSM 路由准确率（有监督）

| 模型 | route_accuracy | success_rate |
|---|---|---|
| deepseek-v4-flash-202605 | — | — |

## 性能与成本对比（Tobi 全量）

| 模型 | throughput(rps) | latency_p50 | latency_p95 | delta_tokens/req |
|---|---|---|---|---|