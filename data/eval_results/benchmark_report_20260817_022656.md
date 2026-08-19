# 企业工单评测报告

生成时间：2026-08-17 02:26:55 UTC

数据集：Tobi-Bueck 客服工单（18537）+ alezzandro/itsm_tickets（900）

评测模型：hy3

## Tobi 有监督分类（官方 GT）

### type（4 类）

| 模型 | accuracy | vs 多数类基线 | vs 随机 |
|---|---|---|---|
| 多数类基线 | 0.4010 | — | +0.1510 |
| 随机基线 | 0.2500 | -0.1510 | — |
| hy3 | — | — | — |

### priority（3 类）

| 模型 | accuracy | vs 多数类基线 | vs 随机 |
|---|---|---|---|
| 多数类基线 | 0.4074 | — | +0.0741 |
| 随机基线 | 0.3333 | -0.0741 | — |
| hy3 | — | — | — |

### queue（10 类）

| 模型 | accuracy | vs 多数类基线 | vs 随机 |
|---|---|---|---|
| 多数类基线 | 0.2917 | — | +0.1917 |
| 随机基线 | 0.1000 | -0.1917 | — |
| hy3 | — | — | — |

## Tobi Agent 行为（无监督）

| 模型 | success_rate | kb_grounding | escalation | answerable | latency_p50 | delta_tok/req |
|---|---|---|---|---|---|---|
| hy3 | 0.6064 | 0.9532 | 0.2739 | 1.0000 | 8.13s | 9211.7 |

## ITSM 路由准确率（有监督）

| 模型 | route_accuracy | success_rate |
|---|---|---|
| hy3 | 0.0000 | 0.0000 |

## 性能与成本对比（Tobi 全量）

| 模型 | throughput(rps) | latency_p50 | latency_p95 | delta_tokens/req |
|---|---|---|---|---|
| hy3 | 0.631 | 8.13s | 61.63s | 9211.7 |