# 企业工单评测报告

生成时间：2026-08-19 09:05:42 UTC

数据集：Tobi-Bueck 客服工单（18537）+ alezzandro/itsm_tickets（900）

评测模型：gemini-3.7-flash-high

## Tobi 有监督分类（官方 GT）

### type（4 类）

| 模型 | accuracy | vs 多数类基线 | vs 随机 |
|---|---|---|---|
| 多数类基线 | 0.4010 | — | +0.1510 |
| 随机基线 | 0.2500 | -0.1510 | — |
| gemini-3.7-flash-high | 0.7264 | +0.3254 | +0.4764 |

### priority（3 类）

| 模型 | accuracy | vs 多数类基线 | vs 随机 |
|---|---|---|---|
| 多数类基线 | 0.4074 | — | +0.0741 |
| 随机基线 | 0.3333 | -0.0741 | — |
| gemini-3.7-flash-high | 0.3653 | -0.0421 | +0.0320 |

### queue（10 类）

| 模型 | accuracy | vs 多数类基线 | vs 随机 |
|---|---|---|---|
| 多数类基线 | 0.2917 | — | +0.1917 |
| 随机基线 | 0.1000 | -0.1917 | — |
| gemini-3.7-flash-high | 0.2883 | -0.0034 | +0.1883 |

## Tobi Agent 行为（无监督）

| 模型 | success_rate | kb_grounding | escalation | answerable | latency_p50 | delta_tok/req |
|---|---|---|---|---|---|---|
| gemini-3.7-flash-high | 1.0000 | 0.9815 | 0.0110 | 1.0000 | 3.5s | 298.3 |

## ITSM 路由准确率（有监督）

| 模型 | route_accuracy | success_rate |
|---|---|---|
| gemini-3.7-flash-high | 1.0000 | 1.0000 |

## 性能与成本对比（Tobi 全量）

| 模型 | throughput(rps) | latency_p50 | latency_p95 | delta_tokens/req |
|---|---|---|---|---|
| gemini-3.7-flash-high | 0.267 | 3.5s | 20.37s | 298.3 |