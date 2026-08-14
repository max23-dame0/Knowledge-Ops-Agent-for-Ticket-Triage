---
doc_id: "REP-DEPLOY-001"
title: "真实部署验证报告：FastAPI + Streamlit + 统一 CLI"
category: "review"
date: "2026-08-14"
status: "delivered"
related:
  - "../00-architecture/manual-review-checklist.md"
  - "pln001-final-report-2026-08-13.md"
---

# 真实部署验证报告（2026-08-14）

## 结论

**部署验证闭环完成**：FastAPI 服务真实进程启动并通过 HTTP 冒烟；12 条人工验收清单全过；Streamlit UI 启动正常。PROGRESS 中长期挂起的"真实部署待执行"项就此关闭。

## 验证环境

| 项 | 值 |
|----|----|
| LLM | 远程 DeepSeek `deepseek-v4-flash` |
| Embedding | SiliconFlow `Qwen/Qwen3-VL-Embedding-8B`（4096 维） |
| FastAPI | uvicorn `src.api.app:app` @ `127.0.0.1:8765`（真实进程） |
| Streamlit | `streamlit run app.py` @ `127.0.0.1:8766`（真实进程，headless） |
| 端口说明 | 8000 被 IDE（CodeBuddy CN.exe, PID 2444）占用 → 服务改用 8765 / UI 改用 8766 |

## 验证结果

### 1. FastAPI HTTP 冒烟（`python -m src.cli api-smoke`）— 4/4 ✅

| 步骤 | 结果 |
|------|------|
| `/healthz` | 200，`status=ok`、`kb_index_available=true`、`ticket_records=20` |
| 错误 API key | 401 拒绝（fail-closed 生效） |
| `/agent/ask` 真实提问 | 200，route=kb，结论引用知识库指引（真实 LLM 全链路） |
| 冒烟汇总 | passed |

### 2. 人工验收清单（`python -m src.cli acceptance`）— 12/12 ✅

五类路由全覆盖：kb（E001/E004/E005）、ticket（E013/E021/E024）、escalation（E025/E031）、clarify（E038/E041）、refuse（E049/E055）全部命中预期路由。

### 3. Streamlit UI 冒烟 ✅

- 服务启动成功，HTTP 200
- 页面可访问（headless 模式，浏览器打开 `http://127.0.0.1:8766` 即可人工验收）

### 4. 回归防线

- pytest **269 passed**（新增 CLI 测试后 +6），ruff 0 告警
- 安装 streamlit 触发 starlette 1.6.0→1.3.1 降级，验证 FastAPI 0.141.1 兼容（app import OK、TestClient 测试全绿、运行中服务无影响）

## 新增/完善：统一 CLI（`python -m src.cli`）

原 CLI 只有单问题模式（`python -m src.agents.main_agent`）。本轮新增统一入口：

| 命令 | 用途 |
|------|------|
| `ask <问题>` | 单问（带 429 重试） |
| `interactive` | REPL 交互模式 |
| `acceptance` | 12 条人工验收清单（镜像 ARCH-004） |
| `api-health --base-url` | 探测运行中服务的 /healthz |
| `api-ask <问题> --api-key` | 单次 HTTP 提问 |
| `api-smoke --api-key` | 完整 HTTP 冒烟（healthz + fail-closed + 真实提问） |

真实部署验证中暴露并修复的 CLI bug：`urllib` 对 401/429/503 抛 HTTPError 导致 smoke 中断 → `_http_json` 捕获并返回 (status, detail)。

## 遗留

| 项 | 状态 |
|----|------|
| 多实例限流需 Redis | 已知架构遗留（单进程内存限流够用） |
| Docker/K8s 容器化部署 | Dockerfile + k8s/deployment.yaml 已就绪，真实 K8s 环境部署不在本地验证范围 |
| 浏览器人工点击验收 | 用户可打开 `http://127.0.0.1:8766` 补一轮视觉验收（可选） |

## 复现命令

```bash
# 1. 启动 API 服务
.venv\Scripts\python.exe -m uvicorn src.api.app:app --host 127.0.0.1 --port 8765
# 2. HTTP 冒烟
.venv\Scripts\python.exe -m src.cli api-smoke --api-key local-dev-key-001 --base-url http://127.0.0.1:8765
# 3. 12 条验收清单
.venv\Scripts\python.exe -m src.cli acceptance
# 4. UI
.venv\Scripts\python.exe -m streamlit run app.py --server.port 8766
```
