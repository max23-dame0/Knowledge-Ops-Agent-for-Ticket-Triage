# 企业工单全量测评 — 中间进度报告

> 生成时间：2026-08-14 17:21 (CST) | 数据源：实时 checkpoint（非最终结果）

---

## 1. 运行状态总览

| 模型 | 端点 | 进程 | Tobi 进度 | 速率 | ETA | 成功率(已完成样本) |
|---|---|---|---|---|---|---|
| **hy3** | knot-proxy (`127.0.0.1:8000`) | PID 4143940 | 8612/18537 (46.5%) | 0.4/s | ~10.5h | 7506/8612 (87.2%) |
| **deepseek-v4-flash-202605** | sub2api (`sub2api.test.tmeoa.com`) | PID 4012226 | 4415/18537 (23.8%) | 0.5/s | ~7.6h | 4415/4415 (**100%**) |

**执行方式**：串行防过载（hy3 走 knot、flash 走独立端点，互不争抢）
**断点保护**：JSONL checkpoint 实时写盘，崩溃可 `--resume` 续跑

---

## 2. 中间指标（实时计算，随进度变化）

### 2.1 hy3（Tobi 行为）

| 指标 | 值 |
|---|---|
| 已处理/总 | 8612 / 18537 (46.5%) |
| 成功/失败 | 7506 / 1106（含历史 502 重试中） |
| 成功率 | 87.2%（重试补齐后预计更高） |
| 失败原因 | HTTP 502: 1014、timed out: 92 |
| 延迟 p50/p95/p99 | 7.03s / 58.3s / 80.7s |
| kb_grounding_rate | **95.1%** |
| escalation_signal_rate | **27.8%** |
| ticket 工具命中 | 2.5% |
| answerable_rate | **100%** |
| delta tokens/请求 | 8017 |

### 2.2 flash-202605（Tobi 行为）

| 指标 | 值 |
|---|---|
| 已处理/总 | 4415 / 18537 (23.8%) |
| 成功/失败 | 4415 / **0** |
| 成功率 | **100%** |
| 延迟 p50/p95/p99 | **1.93s** / 20.0s / 29.1s |
| kb_grounding_rate | **99.4%** |
| escalation_signal_rate | **0.02%**（几乎不升级） |
| ticket 工具命中 | 0.14% |
| answerable_rate | **100%** |
| delta tokens/请求 | **683**（比 hy3 低 11.7 倍） |

### 2.3 分类冒烟（flash-202605，每任务 8-10 条，非全量）

| 任务 | accuracy | 多数类基线 | 随机基线 | 说明 |
|---|---|---|---|---|
| type（4 类） | 71.4% | 40.1% | 25.0% | 优于基线 |
| priority（3 类） | 37.5% | 40.7% | 33.3% | 略低于多数类基线 |
| queue（10 类） | 0-50% | 29.2% | 10.0% | 小样本不稳定，需全量确认 |

---

## 3. 关键发现（中间结论）

1. **flash 全量成功率 100%**：sub2api 端点稳定，无 502；knot 端 hy3 有 502 但重试兜底有效
2. **成本差异显著**：flash 每请求业务 token 683 vs hy3 8017（**约 12 倍差距**），主要来自 knot 常驻上下文和思考开销
3. **行为差异**：hy3 升级倾向明显（27.8% escalation），flash 几乎不升级（0.02%）——可能受 `reasoning_effort`（hy3=no_think vs flash=low）和模型自身倾向影响
4. **kb grounding 都高**：hy3 95.1% / flash 99.4%，符合工单场景预期
5. **分类能力**：type 分类 flash 优于基线（+31pp），queue 10 类分类弱——flash 对细粒度分类能力有限

---

## 4. 预计完成时间

- **flash-202605**：约 7.6h 后完成 Tobi（约 8-15 凌晨 1 点），随后自动 ITSM（900 条约 30 分钟）
- **hy3**：约 10.5h 后完成 Tobi（约 8-15 凌晨 4 点），随后自动 ITSM
- 全部完成预计 **2026-08-15 上午**，随后生成最终完整报告

---

## 5. 最终报告将包含（待全量完成）

- Tobi 行为指标（full）：success_rate / grounding / escalation / answerable / 延迟分位 / token
- Tobi 有监督分类（type/priority/queue）：accuracy + 混淆矩阵 + 基线对比
- ITSM 路由：route_accuracy（label 1→ticket，0/2→kb）
- ITSM 3-way 分类：other/ticket/inquiry accuracy
- 模型横评表 + 基线参照

*本报告由实时 checkpoint 计算，非最终值；最终以 `ticket_full_*.json` + `benchmark_report_*.md` 为准。*
