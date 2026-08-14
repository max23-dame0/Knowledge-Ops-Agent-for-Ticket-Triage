# 企业工单数据集评测 — 云环境运行指南

> **用途**：在 32 核 / 64GB 云主机上全量评测（Tobi-Bueck 20k + ITSM 900）hy3 与 glm-5.2 两个模型
> **代码**：`src/evals/ticket_bench/`（bench_core.py + run_full.py）

---

## 1. 前置准备（云主机）

```bash
# 1. 部署 knot-proxy（本地反代）到云主机，确认 http://127.0.0.1:8000/v1 可访问
#    （config.json 的 model_map 需含 hy3 / glm-5.2 映射）

# 2. 下载数据集到 data/eval_datasets/
#    - Tobi:  data/eval_datasets/tobi_tickets/dataset-tickets-multi-lang-4-20k.csv
#    - ITSM:  data/eval_datasets/itsm_tickets/train.jsonl

# 3. 安装依赖
pip install pandas pyarrow

# 4. 健康检查
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/v1/models
```

## 2. 并发机制设计（核心）

| 参数 | 推荐值 | 依据 |
|------|:--:|------|
| `--workers` | **18**（每模型） | 每个在途请求 spawn 一个 knot-cli 子进程（~1.5GB 内存），双模型总 36 进程 ≈ 54GB，64GB 主机安全 |
| `--timeout` | **30** | 超过 30s 的请求标记跳过，**排到队尾**重试（最多 --max-retries 次） |
| `--max-retries` | 3 | 超时/失败自动重排，避免单点卡死 |
| 双模型并行 | 两个终端各跑一个 | 互不干扰，各自 checkpoint |

**内存公式**：`总并发 = workers_hy3 + workers_glm ≤ (RAM_GB - 8) / 1.5`

**断点续跑**：每个数据集一个 JSONL checkpoint（`data/eval_results/ticket_full_{model}_{dataset}_ckpt.jsonl`），崩溃后 `--resume` 即可继续，不重复已完成样本。

**进度报告**：每 100 条打印 `rate=X/s ETA=Yh`。

## 3. 运行命令

```bash
# 终端 1：hy3
python -m src.evals.ticket_bench.run_full --model hy3 --workers 18 --timeout 30 --max-retries 3

# 终端 2：glm-5.2
python -m src.evals.ticket_bench.run_full --model glm-5.2 --workers 18 --timeout 30 --max-retries 3

# 崩溃后恢复
python -m src.evals.ticket_bench.run_full --model hy3 --workers 18 --timeout 30 --resume
```

## 4. 输出指标

每数据集输出到 `data/eval_results/ticket_full_{model}_{timestamp}.json`：

| 指标 | 说明 |
|------|------|
| `success_rate` | 成功请求占比（含重排重试后） |
| `timeout_count` / `failed_count` / `retries_used` | 超时/失败/重试次数 |
| `latency_p50/p95/p99/max` | 延迟分位 |
| `throughput_rps` / `wall_seconds` | 吞吐 / 总耗时 |
| `total_tokens` / `delta_total_tokens` | 原始 token / **业务 token**（扣除 ~17k knot-cli 常驻基线） |
| `route_accuracy`（ITSM） | 路由准确率（label 1→ticket 工具，0/2→kb） |
| `kb_grounding_rate` / `escalation_signal_rate` / `answerable_rate`（Tobi） | 工单处理质量 |

## 5. 已知注意事项

1. **token 基线**：knot-cli 每个请求自带 ~17k prompt tokens 常驻上下文（系统提示+技能+工具定义），已自动测量并扣除（delta 指标）
2. **内存**：并发过高会内存耗尽（本地 31GB 实测 22 个 knot-cli 即吃光）；云主机 64GB 用 18+18 安全
3. **Tobi 有效样本**：dropna 后 18537 条（非 20000，空字段被过滤）
4. **502 处理**：反代偶发 502，自动重试（指数退避）
