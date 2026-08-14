# 会话交接 — 2026-08-14

> 每次会话结束前填写。下一个会话读取本文件快速恢复上下文。
> 来源：L05 跨会话连续性 + L12 清洁状态

---

## 本轮做了什么

PLN-001 遗留问题修复完成并推送：

1. **E009 修复**：`_resolve_route` 新增 `_looks_like_escalation_policy_query → kb` 分支（升级政策问题从知识库回答，此前落到 clarify 兜底使 KB 政策文档不可达）
2. **E035 修复**：`_maybe_clarify` 两处 context-poor KB 检查加 `and not _looks_like_escalation_query(user_input)`（升级意图不再被"计费异常"式模糊 KB 检查拦截）
3. **E049 修复**：eval_set.csv 标注错误（unsafe=false→true + 行尾脏数据清除），agent 行为本就正确
4. **fabrication 度量细化**：external_bench `oos_fabrication_risk` 增加 `not r["refused"]`（LLM 自行拒答不计幻觉风险）
5. TDD：test_route_rules.py +3 测试（含 clarify_vague 回归）

**结果**：offline eval（66 条，DeepSeek 远程）**五项指标全 100%**（route/tool/clarify/grounding 36/36/refusal），0 失败样本。

## 清洁状态检查

| 检查项 | 状态 |
|--------|:--:|
| pytest tests/（246 passed，+3） | ✅ |
| ruff check src tests app.py | ✅ 0 告警 |
| offline eval（66 条，DeepSeek 远程） | ✅ 五项指标 100% |
| git status | ✅ clean，已推送（b642c21..df53fb5） |
| PROGRESS.md 已更新 | ✅ |
| WIP 登记 | ✅ |

## 仍损坏或未完成

1. **D2 judge 校准**：需用户人工标注约 10-20 条 kb 样本的三维评分，一致性 ≥85% 才启用。
2. **D3 / C5**：等方向 B 产出 / 按需推进。

## 下一步最佳动作

1. D2：抽 10-20 条 kb 样本，跑 judge + 用户人工标注，比对一致性写校准报告
2. 若用户要求，可用 Tobi-Bueck 20k 真实工单跑 ticket_bench 云评测（方向 B 承接）
3. Streamlit UI 冒烟验收（部署验证闭环，PROGRESS 中 FastAPI 真实部署一直待执行）

## 重要上下文（给下一个会话的笔记）

- PLN-001 全部落地：A1-A6 + C1-C4 + D1 已提交推送（df53fb5 为最新）；D2 待标注；D3 等方向 B
- offline eval 已收敛全绿：**失败样本为 0**，A6 下一轮迭代将无反思输入（收敛信号）
- 预检顺序：`_maybe_refuse` → `_maybe_clarify` → LLM（E049 的 route=clarify 是脚本误报，实际 refuse 预检优先）
- `.env` 指向远程 DeepSeek（deepseek-v4-flash）；embedding 走 SiliconFlow Qwen/Qwen3-VL-Embedding-8B（4096 维），索引已按该模型重建
- 切换 embedding 模型必须重建索引，否则维度不匹配直接报错
- 经验池 `data/experience/` 已被 .gitignore 排除；注入开关 `EXPERIENCE_INJECTION_ENABLED` 默认关
- agent 日志走 stderr（logging.StreamHandler），后台跑 eval 时 grep 日志要看 .err 文件
- PowerShell 内联中文会 GBK 截断，验证脚本用文件 + sys.stdout.reconfigure

## 常用命令

```bash
.venv\Scripts\python.exe -m pytest tests/                          # 246 passed
.venv\Scripts\python.exe -m ruff check src tests app.py            # 0 告警
.venv\Scripts\python.exe -m src.evals.run_evals --mode offline     # 66 条五项 100%
.venv\Scripts\python.exe -m src.evals.retrieval_bench              # 检索基线（rerank）
.venv\Scripts\python.exe -m src.improvement.improvement_loop --eval-result-csv data/eval_results/xxx.csv  # A6 loop
```
