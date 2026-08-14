# 企业工单全量测评 — 项目状态交接文档

> 最后更新：2026-08-14 17:25 (CST)
> 供后续 Agent 无缝衔接：请先读本文档，再读 `data/eval_results/progress_report_20260814_1721.md` 了解当前进度。

---

## 0. 项目路径速查

| 项 | 路径 |
|---|---|
| 项目根 | `/data/workspace/Knowledge-Ops-Agent-for-Ticket-Triage/` |
| 云磁盘原始 | `/agentdrive/maxdamema/`（knot-proxy + Knowledge-Ops-Agent-for-Ticket-Triage） |
| 测评代码 | `src/evals/ticket_bench/`（bench_core / run_full / run_classify / run_benchmark / report / bench_config） |
| 测评数据 | `data/eval_datasets/`（tobi_tickets / itsm_tickets） |
| 结果输出 | `data/eval_results/` |
| 监控脚本 | `monitor_bench.py`（项目根） |
| 指标验证 | `verify_metrics.py`、`analyze_ckpt.py`（项目根） |
| knot-proxy | `/data/workspace/knot-proxy/`（后台服务 `127.0.0.1:8000`） |
| knot-cli | `/root/background_agent_cli/bin/knot-cli` |

---

## 1. 当前运行状态（最重要，先看这里）

### 正在运行的任务（截至 2026-08-14 17:21）

| 模型 | 端点 | PID | 日志 | Tobi 进度 | ETA |
|---|---|---|---|---|---|
| hy3 (no_think, 18w, timeout=90) | knot-proxy `127.0.0.1:8000` | **4143940** | `/tmp/bench_hy3.log` | 8612/18537 (46.5%) | ~10.5h |
| deepseek-v4-flash-202605 (low, 8w, timeout=60) | sub2api `http://sub2api.test.tmeoa.com/v1` | **4012226** | `/tmp/bench_flash202605.log` | 4415/18537 (23.8%) | ~7.6h |

### 关键运行命令

```bash
# hy3（knot 端点）
cd /data/workspace/Knowledge-Ops-Agent-for-Ticket-Triage
nohup .venv/bin/python -m src.evals.ticket_bench.run_full \
  --model hy3 --workers 18 --timeout 90 --max-retries 3 \
  --reasoning-effort no_think --resume > /tmp/bench_hy3.log 2>&1 &

# flash-202605（sub2api 端点）
nohup .venv/bin/python -m src.evals.ticket_bench.run_full \
  --model deepseek-v4-flash-202605 --workers 8 --timeout 60 --max-retries 3 \
  --reasoning-effort low \
  --base-url http://sub2api.test.tmeoa.com/v1 \
  --api-key <SUB2API_KEY> \
  > /tmp/bench_flash202605.log 2>&1 &
```

### 监控

```bash
# 前台实时（每秒原地刷新）
.venv/bin/python monitor_bench.py --watch 1 --ansi
# 后台常驻输出
tail -f /tmp/bench_monitor.log
```

### API Key 说明

- **sub2api key**：`<SUB2API_KEY>`
  - 端点：`http://sub2api.test.tmeoa.com/v1`
  - 模型：`deepseek-v4-flash-202605`（快）、`deepseek-v4-pro-202606`（慢 1.5 倍）
  - 该端点 **不支持 `reasoning_effort=no_think`**（枚举：none/minimal/low/medium/high/xhigh/max），**不支持 `max_context_tokens` 参数**，无 knot 17k 基线（baseline≈5 tokens）
- **knot 端点**（hy3）：无需 key，走本地 knot-proxy，模型名 `hy3` / `glm-5.2` / `deepseek-v4-flash` 等（`knot-cli model list` 可查）

---

## 2. 数据集

### Tobi-Bueck（`data/eval_datasets/tobi_tickets/dataset-tickets-multi-lang-4-20k.csv`）

- HuggingFace：`Tobi-Bueck/customer-support-tickets`，合成客服工单，CC BY-NC 4.0
- 有效样本（dropna subject/body 后）：**18537**
- 官方 GT 字段：`type`（Incident/Request/Problem/Change，分布 7434/5358/3839/1906）、`priority`（low/medium/high，3787/7552/7198）、`queue`（10 类，Technical Support 5407 最多）、`language`（EN/DE）、`tag_1..8`
- 无官方 benchmark 指标，官方任务为 text-classification

### ITSM（`data/eval_datasets/itsm_tickets/train.jsonl`）

- HuggingFace：`alezzandro/itsm_tickets`（train 900 + test 150），GPL-3.0
- 字段：`text` + `label`，label 分布均衡 0/1/2 各 300
- 官方无 label 定义；本项目口径（bench_core.py 注释）：**0=other / 1=ticket / 2=inquiry**
- ITSM 路由指标：label 1 → ticket 工具，0/2 → kb

---

## 3. 评测体系（已搭建完成）

### 架构

```
src/evals/ticket_bench/
├── bench_config.py     # 统一配置：数据集/任务/指标/基线（唯一数据源）
├── bench_core.py       # 数据加载、baseline 测量、single_call（含重试）
├── run_full.py         # 全量行为评测：Tobi 18537 + ITSM 900 路由（--resume 断点）
├── run_classify.py     # 有监督分类：Tobi type/priority/queue + ITSM 3-way
├── run_benchmark.py    # 统一入口：编排所有评测 + 生成报告（--report-only 只出报告）
└── report.py           # 报告生成：Markdown + JSON + 多数类/随机基线对比
```

### 统一入口用法

```bash
# 全流程（行为 + 分类 + 报告）
.venv/bin/python -m src.evals.ticket_bench.run_benchmark \
  --model deepseek-v4-flash-202605 --workers 8 --reasoning-effort low \
  --base-url http://sub2api.test.tmeoa.com/v1 --api-key <KEY> \
  --limit 2000   # 分类抽样（全量 5.5 万次调用太久）

# 只生成报告
.venv/bin/python -m src.evals.ticket_bench.run_benchmark --model <m> --report-only
```

### 评测矩阵

| 数据集 | 任务 | 指标 | 监督 |
|---|---|---|---|
| Tobi | Agent 行为 | grounding / escalation / answerable / 延迟分位 / token | 无 |
| Tobi | type 分类 | accuracy + 混淆矩阵 + 基线 | 官方 GT |
| Tobi | priority 分类 | accuracy + 混淆矩阵 + 基线 | 官方 GT |
| Tobi | queue 分类 | accuracy + 混淆矩阵 + 基线 | 官方 GT |
| ITSM | 路由 | route_accuracy | label |
| ITSM | 3-way 分类 | accuracy + 混淆矩阵 | label |

### checkpoint 命名

- 行为：`ticket_full_{model}_{dataset}_ckpt.jsonl`（tobi/itsm）
- 分类：`ticket_classify_{model}_{dataset}_{task}_ckpt.jsonl`
- 结果：`ticket_full_{model}_{ts}.json`、`ticket_classify_{model}_{dataset}_{ts}.json`
- 报告：`benchmark_report_{model}_{ts}.md/.json`

---

## 4. 代码改动记录（本次会话新增/修改）

| 文件 | 改动 | 原因 |
|---|---|---|
| `run_full.py` | `content_len` 字段补齐 + `r.get` 兼容 | 修复 KeyError 崩溃 |
| `run_full.py` | hash → `hashlib.md5(text[:80])` 稳定 ID | 修复跨进程 resume 失效（PYTHONHASHSEED 随机化） |
| `run_full.py` | resume 只跳过 ok 行，失败行重试 | 修复失败样本永久丢失 |
| `run_full.py` | `--reasoning-effort` / `--base-url` / `--api-key` 参数 | 支持多端点多模型 |
| `bench_core.py` | `single_call`/`get_baseline` 支持 api_key/base_url/reasoning_effort | 同上 |
| `run_classify.py` | 新建：Tobi 分类 + ITSM 3-way，429/502/超时重试 | 有监督评测体系 |
| `bench_config.py` / `report.py` / `run_benchmark.py` | 新建：统一配置/报告/编排 | 统一评测体系 |
| `monitor_bench.py` | 新建：每秒增量监控（原地刷新/追加双模式） | 实时看进度 |
| `verify_metrics.py` / `analyze_ckpt.py` | 新建：指标独立验证/中间统计 | 指标正确性保障 |
| `salvage_ckpt.py` | 新建：旧 checkpoint 迁移（已用，数据不可救） | 第一轮数据恢复尝试 |

---

## 5. 历史事故与教训（务必阅读）

### 事故 1：第一轮并行方案数据报废（2026-08-13 晚 ~ 08-14 凌晨）
- **现象**：hy3+glm-5.2 双模型各 18 workers 并行，36 并发打爆 knot 后端，15000+ 条 HTTP 502
- **教训**：**严禁双模型并行打同一 knot 端点**（测速 26 并发即触发过载）；串行或走独立端点
- 报废数据备份于 `data/eval_results/backup_resume_fail/`（flash ok 仅 3032/18537、hy3 3269/18537）

### 事故 2：`content_len` KeyError 崩溃（2026-08-14 10:17）
- 指标计算阶段 `r["content_len"]` 直接索引崩溃，Tobi 18537×2 条统计丢失
- 已修复（补字段 + `r.get`），resume 补跑 ITSM

### 事故 3：resume 失效导致 tobi 重跑（2026-08-14 上午）
- 内置 `hash()` 跨进程随机化（PYTHONHASHSEED），新旧 sample_id 永不匹配
- 已修复（md5 稳定哈希），**resume 只跳过 ok 行**

### 事故 4：hy3 超时风暴（2026-08-14 15:00）
- flash 任务启动后系统负载升高（load 27），hy3 30s 超时太紧，最新 200 条 187 失败
- 已修复：hy3 改 `--timeout 90` + resume 重启

### 通用教训
- 测速/评测任务**不可并行打同一端点**（触发限流风暴）
- 并发建议：knot 端点单模型 ≤18 workers；sub2api 端点 flash ≤8 workers（超过 429 飙升）
- `--timeout` 宁大勿小（后端慢时 30s 会造成大量假超时）

---

## 6. 下一步指引（后续 Agent 待办）

### 短期（全量完成后）
1. 等两个 run_full 进程自然结束（各自输出 `saved: ticket_full_*.json`）
2. 生成最终报告：
   ```bash
   .venv/bin/python -m src.evals.ticket_bench.run_benchmark --model hy3 --report-only
   .venv/bin/python -m src.evals.ticket_bench.run_benchmark --model deepseek-v4-flash-202605 --report-only
   ```
3. 汇总两份报告 + 模型对比，输出最终评测总结

### 中期（可选增强）
- 跑 Tobi 分类全量或抽样（`--limit 2000`）补全有监督指标
- ITSM 3-way 分类（`--dataset itsm`）
- 用 `tag_1..8` 做多标签分类评测
- 对比 deepseek-v4-pro-202606（已有 key，慢但更准）

### 运维
- knot-proxy 是 nohup 后台进程，环境重启后需重启：
  ```bash
  cd /data/workspace/knot-proxy && nohup /usr/bin/python3.8 knot_proxy.py > /tmp/knot_proxy_stdout.log 2>&1 &
  ```
- 每小时自动化任务「工单测评进度检查」检查进度（平台最小粒度是小时，且多次超时，需手动兜底）
- 监控脚本后台常驻：PID 见 `ps aux | grep monitor_bench`，日志 `/tmp/bench_monitor.log`

---

## 7. 环境信息

- Python venv：项目内 `.venv`（Python 3.14.3，路径 `/root/.workbuddy/binaries/python/versions/3.14.3/bin/python3` 创建）
- 机器：246GB 内存 / 32+ 核，实际内存远超指南假设（瓶颈在模型后端限流而非内存）
- knot-cli 模型列表：`/root/background_agent_cli/bin/knot-cli model list`
- knot-proxy 配置：`/data/workspace/knot-proxy/config.json`（knot_cli 已指向 Linux 路径）
- 工作记忆：`/data/workspace/.codebuddy/memory/2026-08-13.md`、`2026-08-14.md`（含全部决策与事故记录）
