# 会话交接 — 2026-08-14（晚间）

> 每次会话结束前填写。下一个会话读取本文件快速恢复上下文。

---

## 本轮做了什么

1. **D2 judge 校准收尾**：两轮校准（盲评 66.7% → 证据感知 50%）均 <85%，judge 确认不启用（D007 约束）；根因是评分标准结构性不一致（judge 判"证据列表存在"、人工判"回答复用证据"），不再追调 prompt（防过拟合）
2. **统一 CLI 开发**（`python -m src.cli`）：ask / interactive / acceptance（12 条镜像 ARCH-004）/ api-health / api-ask / api-smoke
3. **真实部署验证闭环**：uvicorn 真实进程 + HTTP 冒烟 + 12/12 验收 + Streamlit UI，报告 REP-DEPLOY-001
4. 验证中修复 CLI 的 urllib HTTPError（401/429/503）处理 bug

## 清洁状态检查

| 检查项 | 状态 |
|--------|:--:|
| pytest tests/（269 passed） | ✅ |
| ruff check src tests app.py | ✅ 0 告警 |
| 真实部署验证（FastAPI + 验收 12/12 + Streamlit） | ✅ 已完成 |
| git status | ✅ clean，已推送（origin/main ..8cb23c4） |
| PROGRESS.md 已更新 | ✅ |
| WIP 登记 | ✅ |

## 仍损坏或未完成

1. **D3**：真实工单样本纳入回归集——等方向 B 云侧产出（用户处进行中）
2. **C5** 语义分块：计划可选，暂缓
3. 浏览器人工点击验收：用户可打开 `http://127.0.0.1:8766` 补视觉验收（可选）

## 下一步最佳动作

1. 方向 B 云测评完成后：D3 把真实样本纳入回归集
2. 若 judge 要启用（可选）：先对齐评分 rubric + 独立校准集

## 重要上下文（给下一个会话的笔记）

- **部署验证已闭环**（PROGRESS 长期挂起项关闭）：命令见 documents/02-review/deployment-verification-report-2026-08-14.md
- **端口坑**：8000 被 IDE（CodeBuddy CN.exe）占用；本地服务用 8765（API）/ 8766（Streamlit）；uvicorn 起 8000 会 Errno 10048
- **依赖坑**：装 streamlit 会把 starlette 1.6.0 降到 1.3.1（与 FastAPI 0.141.1 兼容已验证）；venv 里有残留无效分发 ~rotobuf（pip 警告可忽略）
- **CLI 入口**：`python -m src.cli <command>`；acceptance 跑真实 LLM 约 3-4 分钟
- 背景进程验证后务必 Stop-Process（uvicorn/streamlit PID 通过 netstat -ano | findstr ":8765 :8766" 找）
- PLN-001 现状：A1-A6 ✅、C1-C4 ✅、D1-D2 ✅（judge 不启用）、D3 挂起；offline eval 五项 100%；rerank recall@1 0.90→1.00
- `.env`：LLM=远程 DeepSeek（deepseek-v4-flash）；embedding=SiliconFlow Qwen3-VL-8B（4096 维，索引已对齐重建）

## 常用命令

```bash
.venv\Scripts\python.exe -m pytest tests/                          # 269 passed
.venv\Scripts\python.exe -m ruff check src tests app.py            # 0 告警
.venv\Scripts\python.exe -m src.cli ask "问题"                      # 单问
.venv\Scripts\python.exe -m src.cli acceptance                      # 12 条验收清单
.venv\Scripts\python.exe -m uvicorn src.api.app:app --port 8765     # 起 API
.venv\Scripts\python.exe -m src.cli api-smoke --api-key local-dev-key-001 --base-url http://127.0.0.1:8765
.venv\Scripts\python.exe -m streamlit run app.py --server.port 8766 # 起 UI
```
