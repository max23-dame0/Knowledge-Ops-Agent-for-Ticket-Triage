# knowledge-ops-agent

A minimal Python agent project for support-style workflows: **knowledge base Q&A, ticket lookup, and escalation suggestion**, plus clarification and refusal guardrails. Built as a clear, inspectable demo of agent routing, tool use, structured outputs, and eval-driven iteration. **Not production-ready.**

## Features

- KB Q&A over local markdown docs (`data/kb_docs/`) with local RAG (sentence-transformers + FAISS/HNSW + BM25 hybrid)
- Ticket lookup from local JSON (`data/tickets.json`) with lenient ticket ID parsing
- Rule-based escalation draft generation
- Routes: `kb` / `ticket` / `escalation` / `clarify` / `refuse`
- Structured outputs (`AgentAnswer`) consumed by CLI, Streamlit UI, and offline eval
- FastAPI service (`/healthz`, `/agent/ask`), structured logging, circuit breaker + LRU cache
- Offline eval loop (offline + regression modes) and external benchmarks (prompt-injections / clinc_oos)

## Quick Start

```bash
# 1. Configure environment (LLM_MODEL_ID / LLM_API_KEY / LLM_BASE_URL, OpenAI-compatible)
cp .env.example .env

# 2. Install dependencies
python -m venv .venv && .venv\Scripts\activate
python -m pip install -r requirements.txt

# 3. Build the local KB index
.venv\Scripts\python.exe -m src.rag.build_index

# 4. Run the CLI agent
.venv\Scripts\python.exe -m src.agents.main_agent "VPN 登录失败提示 token 过期怎么办"

# 5. Run the Streamlit demo
streamlit run app.py
```

Run offline eval:

```bash
.venv\Scripts\python.exe -m src.evals.run_evals --mode regression   # quick smoke checks
.venv\Scripts\python.exe -m src.evals.run_evals --mode offline     # full labeled run
```

Run tests and lint:

```bash
python -m pytest tests/
python -m ruff check src tests app.py
```

## Project Structure

```text
knowledge-ops-agent/
├── app.py                     # Streamlit demo entry
├── AGENTS.md                  # Agent entry router (operations manual)
├── PROGRESS.md                # progress board
├── DECISIONS.md               # architecture decision records (D001-D006)
├── README.md / README_CN.md   # lean entry points (EN / 中文)
├── documents/                 # documentation corpus (see documents/README.md)
├── data/                      # kb_docs / tickets.json / eval_set.csv / index / eval_results
├── src/
│   ├── agents/                # main_agent (decision owner) + retrieval_agent + guardrails
│   ├── api/                   # FastAPI service
│   ├── evals/                 # run_evals / metrics / error_analysis / external_bench
│   ├── rag/                   # chunking / build_index / retrieve / hybrid
│   ├── repositories/          # thread-safe in-memory repositories
│   ├── tools/                 # kb_search / ticket_tools / escalation_tools
│   └── utils/                 # config / logging / resilience
└── tests/                     # pytest suite
```

## Documentation

Detailed docs live in the `documents/` corpus; start at [documents/README.md](documents/README.md):

| 我想... (Chinese) | 文档 |
|------|------|
| 架构与路由设计 | `documents/00-architecture/architecture.md` |
| 工具入参出参 | `documents/00-architecture/tools.md` |
| 评测方法与命令 | `documents/00-architecture/evaluation.md` |
| Demo / 面试演示问题 | `documents/04-reports/demo-scenarios.md` |
| UI 冒烟验收清单 | `documents/00-architecture/manual-review-checklist.md` |
| 评测报告 | `documents/02-review/` |

## Multi-language

- [README in Chinese (中文版)](./README_CN.md)
