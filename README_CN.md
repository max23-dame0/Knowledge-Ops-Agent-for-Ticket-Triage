# knowledge-ops-agent（中文版）

一个面向支持场景的轻量 Agent 项目：**知识库问答、工单查询、升级建议**，外加澄清与拒答保护行为。刻意保持小而清晰，用于展示 agent 路由、工具调用、结构化输出和 eval-driven iteration。**非 production-ready。**

## 功能特性

- 基于 `data/kb_docs/` 的本地知识库问答（sentence-transformers + FAISS/HNSW + BM25 混合检索）
- 基于 `data/tickets.json` 的工单查询，支持宽松 ticket ID 识别
- 基于规则的升级建议草稿生成
- 五类路由：`kb` / `ticket` / `escalation` / `clarify` / `refuse`
- 结构化输出（`AgentAnswer`），供 CLI、Streamlit UI、离线评测消费
- FastAPI 服务（`/healthz`、`/agent/ask`）、结构化日志、熔断 + LRU 缓存
- 离线评测闭环（offline + regression 双模式）与外部评测（prompt-injections / clinc_oos）

## 快速开始

```bash
# 1. 配置环境变量（LLM_MODEL_ID / LLM_API_KEY / LLM_BASE_URL，OpenAI 兼容端点）
cp .env.example .env

# 2. 安装依赖
python -m venv .venv && .venv\Scripts\activate
python -m pip install -r requirements.txt

# 3. 构建本地 KB 索引
.venv\Scripts\python.exe -m src.rag.build_index

# 4. 运行 CLI Agent
.venv\Scripts\python.exe -m src.agents.main_agent "VPN 登录失败提示 token 过期怎么办"

# 5. 运行 Streamlit 演示页
streamlit run app.py
```

运行离线评测：

```bash
.venv\Scripts\python.exe -m src.evals.run_evals --mode regression   # 快速回归冒烟
.venv\Scripts\python.exe -m src.evals.run_evals --mode offline     # 全量标注集评测
```

运行测试与 lint：

```bash
python -m pytest tests/
python -m ruff check src tests app.py
```

## 项目结构

```text
knowledge-ops-agent/
├── app.py                     # Streamlit 演示入口
├── AGENTS.md                  # Agent 入口路由器（操作手册）
├── PROGRESS.md                # 项目进度看板
├── DECISIONS.md               # 架构决策记录（D001-D006）
├── README.md / README_CN.md   # 精简入口（英文 / 中文）
├── documents/                 # 文档语料（见 documents/README.md）
├── data/                      # kb_docs / tickets.json / eval_set.csv / index / eval_results
├── src/
│   ├── agents/                # main_agent（决策 owner）+ retrieval_agent + guardrails
│   ├── api/                   # FastAPI 服务
│   ├── evals/                 # run_evals / metrics / error_analysis / external_bench
│   ├── rag/                   # chunking / build_index / retrieve / hybrid
│   ├── repositories/          # 线程安全内存仓储
│   ├── tools/                 # kb_search / ticket_tools / escalation_tools
│   └── utils/                 # config / logging / resilience
└── tests/                     # pytest 单测
```

## 文档索引

详细文档统一存放在 `documents/` 语料库，入口：[documents/README.md](documents/README.md)

| 我想... | 文档 |
|------|------|
| 架构与路由设计 | `documents/00-architecture/architecture.md` |
| 工具入参出参 | `documents/00-architecture/tools.md` |
| 评测方法与命令 | `documents/00-architecture/evaluation.md` |
| Demo / 面试演示问题 | `documents/04-reports/demo-scenarios.md` |
| UI 冒烟验收清单 | `documents/00-architecture/manual-review-checklist.md` |
| 评测报告 | `documents/02-review/` |

## 多语言

- [README in English](./README.md)
