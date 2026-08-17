# knowledge-ops-agent — Agent 操作手册

> **角色**：路由器（80-200 行）。详细规范见专题文档和分层规则。
> **上下文预算**：32768 字节
> **最后更新**：2026-08-12

## Setup & Commands

```bash
.venv\Scripts\python.exe -m src.rag.build_index        # 构建 KB 索引（数据变更后必跑）
.venv\Scripts\python.exe -m src.evals.run_evals --mode regression   # 回归冒烟测试
streamlit run app.py                                    # 启动 Streamlit UI
.venv\Scripts\python.exe -m src.agents.main_agent "VPN 登录失败提示 token 过期怎么办"   # CLI 运行
.venv\Scripts\python.exe -m src.evals.run_evals --mode offline     # 离线评估
.venv\Scripts\python.exe -m src.evals.error_analysis    # 最新评估结果错误分析
.venv\Scripts\python.exe -m src.evals.replay_runner replay    # 离线回放 golden 决策（无需 LLM）
.venv\Scripts\python.exe -m src.evals.replay_runner promote   # 把真实运行轨迹晋升为 golden
```

## 会话工作流

### 上班（每次新会话开始，强制按此顺序执行）

1. 读取 `.codebuddy/memory/MEMORY.md`（项目认知 + 上次记忆）
2. 读取本文件（操作手册 + 硬约束 + 上下文预算）
3. 读取 `PROGRESS.md`（当前进度、活跃任务看板、未提交改动清单、blocker）
4. 读取 `DECISIONS.md`（已有决策，不要推翻）
5. 根据当前任务模块，读取 `.codebuddy/rules/` 下对应规则

### 下班（每次会话结束前，缺一不可）

1. 更新 `PROGRESS.md`（完成内容、仍有问题、下一步）
2. 若有新决策 → 记录到 `DECISIONS.md`
3. 将重要发现写入 `.codebuddy/memory/MEMORY.md` 的 Auto Memory 区域
4. 填写 `.codebuddy/harness/session-handoff.md`（**禁止留空占位符**）
5. 检查 git status：清洁（已提交）或**登记到「未提交改动清单」**
6. **WIP 显式登记**：把当前并行任务写回「活跃任务看板」（切换任务前必须写回状态与下一步，不允许脑子记）

### 清洁状态检查（L12 — "做完"的硬性定义）

以下六项**全部通过**才算完成：

| # | 检查项 | 命令/方式 | 状态 |
|:--|------|------|:--:|
| 1 | 索引构建通过（数据变更后） | `.venv\Scripts\python.exe -m src.rag.build_index` | ⬜ |
| 2 | 回归测试通过（基线一致，已知失败须具名） | `... run_evals --mode regression` | ⬜ |
| 3 | 无 lint 告警 | `python -m py_compile` / ruff（如有） | ⬜ |
| 4 | git status clean 或已登记未提交清单 | `git status` | ⬜ |
| 5 | PROGRESS.md 已更新（活跃任务看板 + 未提交清单同步） | 检查更新日期 | ⬜ |
| 6 | **部署后验证闭环**：已部署目标环境并通过冒烟/E2E，或显式记录「未验证原因 + 预计验证时间」 | 部署/接口验证 | ⬜ |

> 第 6 项杜绝"本地 ✅ 但生产未验证"的早停：凡只标本地通过、未走部署验证的任务，状态不得写 ✅。
> 本项目的"部署"特指 Streamlit UI 冒烟验收（见 `manual_review_checklist.md`）。

## 项目结构

```
knowledge-ops-agent/
├── app.py                     # Streamlit 演示入口（UI 冒烟验收）
├── data/
│   ├── kb_docs/               # 知识库 markdown 源文档（10 篇）
│   ├── tickets.json           # 工单数据（TKT-1001 ~ 1007+）
│   ├── eval_set.csv           # 离线评估集
│   ├── index/                 # FAISS 索引产物（kb_index.faiss + kb_metadata.json）
│   └── eval_results/          # 评估输出（.gitignore 排除）
├── src/
│   ├── agents/                # main_agent（决策 owner）+ retrieval_agent（证据层）+ guardrails
│   ├── evals/                 # run_evals / metrics / error_analysis
│   ├── rag/                   # chunking / build_index / retrieve
│   ├── tools/                 # kb_search / ticket_tools / escalation_tools
│   └── utils/                 # config（.env 加载）/ logging
└── manual_review_checklist.md # UI 手动验收清单
```

## 分层规则加载

编写代码前加载对应规则：

| 规则文件 | 生效条件 | 路径 |
|---------|---------|------|
| global.md | 始终生效 | `.codebuddy/rules/global.md` |
| agents.md | `**/agents/**` | `.codebuddy/rules/agents.md` |
| evals.md | `**/evals/**` | `.codebuddy/rules/evals.md` |
| rag.md | `**/rag/**` | `.codebuddy/rules/rag.md` |
| tools.md | `**/tools/**` | `.codebuddy/rules/tools.md` |
| utils.md | `**/utils/**` | `.codebuddy/rules/utils.md` |

**加载策略**：代码涉及多个模块时，加载所有命中 glob 规则的**并集**。

## Coding Standards

- Python 3.11+，使用 `from __future__ import annotations` + 类型注解；结构化输出一律用 pydantic `BaseModel`
- 每个模块文件必须有一句话 docstring；函数用一句话 docstring 说明职责
- 日志统一用 `src/utils/logging.py` 的 `get_logger`，格式 `key=value`（如 `tool_call=search_kb | query=...`）
- 工具函数返回结构化 dict（由 pydantic 模型 `model_dump()` 产出），禁止裸 dict 自由发挥
- 环境配置只从 `.env` / 环境变量读取（`src/utils/config.py`），**禁止硬编码 API key / URL**
- 中文 UI/交互文案保留中文；代码标识符用英文

## Do Not（硬约束）

| # | 约束 | why | when | when_remove |
|:--:|------|-----|------|------|
| 1 | 不提交 `.env`、API key、任何密钥 | 密钥泄露即安全事件 | 任何时候 | 永不 |
| 2 | `main_agent` 是唯一顶层决策 owner；不得让 retrieval_agent 拥有路由/决策权 | 保持单决策者架构，避免漂移为多 agent 混战 | 修改 agents 架构时 | 架构决策 D004 变更时 |
| 3 | 不改动 `data/kb_docs/`、`data/tickets.json` 的原始语义（仅可追加） | 数据是评估与 demo 的锚点 | 需要修改样例数据时 | 数据源切换为真实后端时 |
| 4 | 不引入非 OpenAI 兼容调用方式（保持 `OpenAIChatCompletionsModel` 通道） | 兼容第三方提供商（MiniMax 等） | 修改 LLM 接入时 | 决策 D003 变更时 |
| 5 | `data/eval_results/` 产物不入库 | 评估输出是临时产物 | 提交代码时 | 永不（gitignore 已固化） |
| 6 | 不输出 `<think>` / 推理过程 / Markdown 标题到最终回答 | 违反 MAIN_AGENT_INSTRUCTIONS 第 15 条 | 修改 agent 输出时 | 决策变更时 |
| 7 | 修改 `requirements.txt` 前先确认：是否真的需要新依赖（当前 7 个依赖已覆盖全部功能） | 保持依赖最小化 | 添加依赖时 | 功能确实需要时 |

## 专题文档索引

| 文档 | 用途 | 何时读 |
|------|------|--------|
| `README.md` / `README_CN.md` | 架构全貌、运行步骤、demo 场景、评估说明 | 新会话初期 |
| `manual_review_checklist.md` | Streamlit UI 手动验收清单（冒烟测试步骤） | 验收/部署验证时 |
| `.codebuddy/harness/tech-traps.md` | 冷记忆：技术陷阱与已知限制 | 遇到对应技术时 |
| `.codebuddy/harness/session-handoff.md` | 会话交接 | 上班/下班 |
| `.codebuddy/harness/context-budget.md` | 上下文预算策略 | 上下文紧张时 |

## 上下文预算

本文件 + MEMORY.md + 规则文件的总加载量 ≤ 32768 字节。超出时优先精简 MEMORY.md 的历史记录，其次按需加载规则。
