# PROGRESS — 项目当前进度

> 最后更新：2026-08-13
> **上班必读**：本文件 + DECISIONS.md

## 活跃任务看板（WIP 显式登记）

> 允许并行，但每个活跃任务必须在此登记一行；切换前写回状态与下一步。

### PLN-001：Agent 自我改进 + RAG 深化 + 评测升级（2026-08-13 启动）

> 计划：`documents/01-planning/agent-self-improvement-rag-plan-2026-08-13.md`
> 设计：`documents/01-planning/features/agent-self-improvement-tech-design-2026-08-13.md`

| # | 任务 | 依赖 | 状态 | 验证 | 下一步 |
|:--:|------|------|:--:|------|------|
| A1 | 失败轨迹采集器 | 无 | ✅ 已提交（f795876，6 单测） | pytest | - |
| A2 | 反思器（PII 清洗 + LLM 兜底） | A1 | ✅ 已提交（97cb5f8，6 单测） | pytest(mock LLM) | - |
| A3 | 经验池（jsonl/容量/去重/检索） | A2 | ✅ 已提交（c1d850e，6 单测） | pytest | - |
| A4 | 检索增强注入（开关可关闭） | A3, C1 | ✅ 已提交（5b2b9d1，6 单测+主链路集成） | pytest | - |
| A5 | 自我改进门控（安全硬 gate） | A4 | ✅ 已提交（82a7781，5 单测） | pytest | - |
| A6 | 自动迭代 loop（端到端） | A5 | ✅ 已提交（b945d85，6 单测 mock） | pytest；真实端到端待 LLM 端点 | 需 knot-proxy 或 DeepSeek |
| C1 | CrossEncoder rerank | 无 | ✅ 已提交（a810077，3 单测+真实链路冒烟） | pytest + C4 对比 | - |
| C2 | 相关性门控 + 低置信信号 | C1 | ✅ 已提交（a810077，6 单测） | pytest | - |
| C3 | 查询改写（规则式） | 无 | ✅ 已提交（8f3c11c，5 单测+检索链路接入） | pytest | - |
| C4 | 检索评测集 + recall@k/MRR 基准 | C1 | ✅ 已提交（c90a323，8 单测+基线报告） | recall@1 0.9→1.0 / MRR 0.95→1.0 | - |
| C5 | 语义分块 | C1-C4 | ⏸ 暂缓（计划可选） | - | - |
| D1 | semantic grader（三维质量评分） | 无 | ✅ 已提交（d761314，5 单测 mock） | pytest；真实端点比对待做 | - |
| D2 | judge 校准报告 | D1 | ⬜ | 一致性≥85% | 需用户人工标注 |
| D3 | 真实工单样本纳入回归集 | B(云) | ⏸ 挂起 | - | 等方向 B |

### 历史看板（已完成）

| # | 任务 | 阶段 | 状态 | 下一步 | 阻塞 |
|:--:|------|------|:--:|------|------|
| 1 | 本地端点工具型评测（regression 11 + offline 66，本地反代支持 tools 后） | 已完成 | ✅ 已提交（报告落盘） | regression 11/11、offline route 97%、grounding 100% | 无 |
| 2 | 本地反代 tools 支持验证（用户修改后） | 已完成 | ✅ 五路由工具调用全部正常 | 无 | 无 |
| 3 | 扩大覆盖评测（253 条全量：注入 60/良性 56 全量 + JailbreakBench 100 + OOS 30 + 域内 7，本地端点） | 已完成 | ✅ 已提交（863ddb0） | 注入 100% / Jailbreak 100% / OOS 100% 全绿 | 无 |
| 4 | 本地 API 接入（knot-proxy 优先，远程保留，--endpoint 切换） | 已完成 | ✅ 已提交（863ddb0，.env 本地配置不入库） | 本地端点可全量替代远程（含工具型） | 无 |
| 5 | 外部数据集评测（prompt-injections/clinc_oos 下载 + 评测脚本 + 报告） | 已完成 | ✅ 已提交（dc81f39/fd25830） | P2 建议（空证据降级/误伤细分）可选推进 | 无 |
| 6 | P1 加固（fallback kb→clarify + 多语种注入检测） | 已完成 | ✅ 已提交（dc81f39） | 复测：注入拒答 100%、幻觉风险 0 | 无 |
| 7 | 企业就绪度修复 Phase A（密钥清理/单测/CI） | 已完成 | ✅ 已提交（afe838a/b1ed522/9dab6ed） | 无 | 无 |
| 8 | 企业就绪度修复 Phase B（日志/Repository/熔断缓存/API服务/部署） | 已完成 | ✅ 已提交（16d3e32..4c27fe8） | 部署验证需真实环境 | 无 |
| 9 | 企业就绪度修复 Phase C（混合检索/安全闸/审计/多轮会话） | 已完成 | ✅ 已提交（d7b593d..3a37515） | CI 全依赖跑 faiss 单测 | 无 |
| 10 | 企业就绪度差距分析文档 | 已完成 | ✅ 已提交（含修复完成记录） | 无 | 无 |
| 11 | Harness 环境首次搭建（AGENTS/MEMORY/PROGRESS/DECISIONS/rules/handoff） | 已完成 | ✅ 已提交（3a545fa） | 无 | 无 |
| 12 | 核心功能基线（main_agent + RAG + tools + eval） | 已完成 | ✅ 已提交（git log: 0c254fa 及之前） | 无 | 无 |

## 当前验证状态

| 检查项 | 状态 |
|------|------|
| `pytest tests/`（**227 passed / 0 skipped**，faiss 重依赖已装真跑） | ✅ 已验证（2026-08-13） |
| `ruff check src tests app.py` | ✅ 0 错误（2026-08-12） |
| `.venv\Scripts\python.exe -m src.rag.build_index`（HNSW 默认，19 chunks，embedding=SiliconFlow Qwen/Qwen3-VL-Embedding-8B 4096 维） | ✅ 已重建 + 检索冒烟通过（vpn→vpn_login 0.64 strong） |
| `... run_evals --mode regression`（11 用例，DeepSeek 端点） | ✅ 11/11 100%（2026-08-12） |
| `... run_evals --mode offline`（66 用例含 6 对抗） | ✅ route 98.5% / grounding 100% / refusal 98.5%（2026-08-12） |
| FastAPI 冒烟（/healthz、/agent/ask） | ✅ TestClient 已验证；真实部署待执行 |
| git status / 未提交清单 | ✅ 已提交并推送（origin/main 3a545fa..cc3c3fb，2026-08-13） |
| 当前 blocker | 无 |

## 未提交改动清单（与 git 强一致）

> 规则：标记 ✅ 完成的任务，其代码**必须已 commit**；仅本地验证未提交的，状态一律写「🟡 已验证待提交」并登记于此。

| 改动 | 状态 | 计划 commit | 关联任务 |
|------|:--:|------|------|
| Embedding API 通道（SiliconFlow Qwen/Qwen3-VL-Embedding-8B）：src/rag/embedding.py 新增 + config.py EmbeddingSettings + kb_repository/build_index/retrieve 接入 + .env.example 模板；索引已按新模型重建，227 单测绿 | 🟡 已验证待提交 | 下一次 commit | 基础设施 |
| Harness 文件（AGENTS.md / PROGRESS.md / DECISIONS.md / .codebuddy/） | ✅ 已提交（3a545fa） | 已完成 | - |
| 企业就绪度差距分析文档（含修复完成记录）+ PROGRESS 更新 | ✅ 已提交（ad69833/41f457d） | 已完成 | 1-4 |
| 文档治理：README/README_CN 精简为入口（~90 行）+ documents/ 语料体系（架构/工具/评测/验收清单/演示场景 + 五要素索引）+ 02-review 补 frontmatter + 引用修复 | ✅ 已提交（3763dc1） | 已完成 | 文档治理 |

## 整体进度

| Phase | 内容 | 状态 | 完成日期 |
|:--|:--|:--:|:--:|
| P0 | 项目骨架与支持 agent 基线 | ✅ | 2026-03（commit 7322de3） |
| P1 | 核心路由（kb/ticket/escalation/clarify/refuse）与边界规则 | ✅ | 2026-03（commit a65d5db 等） |
| P2 | RAG 管道（chunking + embeddings + FAISS） | ✅ | 2026-03 |
| P3 | 工具层（search_kb / get_ticket_status / create_escalation_draft） | ✅ | 2026-03 |
| P4 | 评估流水线（offline + regression + error_analysis） | ✅ | 2026-03（commit 301e51d） |
| P5 | 文档（README 精简入口 + documents/ 语料体系 + 验收清单） | ✅ | 2026-08（commit 0c254fa） |
| P6 | Harness 环境搭建 | 🟡 待提交 | 2026-08-12 |

## 阻塞项

无。

## 最近会话记录（三行摘要，详情见 daily memory）

| 日期 | 做了什么（一行） | 验证 | 下一步 | 日志 |
|------|---------|:--:|------|
| 2026-08-13 | Embedding 切换为 SiliconFlow API（最终 Qwen/Qwen3-VL-Embedding-8B，4096 维；先 bge-m3 后改 Qwen3-VL）：新增 src/rag/embedding.py（API 客户端 + 本地兜底 + L2 归一化）、config.py 加 EmbeddingSettings、kb_repository/build_index/retrieve 接入统一接口、.env/.env.example 配置；重建 HNSW 索引（19 chunks） | API 连通 ✅、检索冒烟 vpn→0.64 strong、pytest 227 passed | 待提交（登记未提交清单） | `.codebuddy/memory/2026-08-13.md` |
| 2026-08-13 | PLN-001 交付：自我改进引擎 A1-A6 全链路 + RAG 深化 C1-C4（CrossEncoder rerank/相关性门控/查询改写/检索评测）+ 评测升级 D1（semantic grader），ADR D007，9 个 commit | pytest 233 passed（+69）/ ruff 0 / rerank recall@1 0.90→1.00、MRR 0.95→1.00 | D2 需用户标注；A6 真实端到端待 LLM 端点 | `.codebuddy/memory/2026-08-13.md` |
| 2026-08-13 | 文档治理：README×2 从 640/623 行瘦身为 ~90 行精简入口，详细内容拆分至 documents/ 语料（00-architecture×4 + 04-reports×1 + 五要素索引），02-review×5 补 frontmatter，AGENTS/DECISIONS/PROGRESS 引用修复，manual_review_checklist 迁入 documents/ | 链接全部有效、无残留引用 | 已提交（3763dc1）并推送 origin/main（3a545fa..cc3c3fb） | `.codebuddy/memory/2026-08-13.md` |
| 2026-08-13 | 本地端点工具型评测：反代支持 tools 后跑 regression 11 条 + offline 66 条，报告落盘 documents/02-review/local-endpoint-tool-eval-report-2026-08-13.md | regression 11/11（100%）、offline route 97.0%/grounding 100%/refusal 98.5% | E009/E021/E049 三点可选优化 | `.codebuddy/memory/2026-08-13.md` |
| 2026-08-12 | 外部数据集评测闭环：下载 deepset/prompt-injections + clinc_oos → 评测脚本 → 初测（注入拒答 80%、幻觉敞口 96.7%）→ P1 加固（fallback clarify + 多语种注入正则）→ 复测（注入拒答 100%、幻觉风险 0、规则层拦截 3.7x） | pytest 171 passed / 评测全指标改善 | P2 建议可选；Docker/K8s 部署验证 | `.codebuddy/memory/2026-08-12.md` |
| 2026-08-12 | 端到端验证闭环：安装 faiss 全依赖 → pytest 164/164 全绿 → HNSW 索引重建 + 混合检索冒烟 → DeepSeek 端点 regression 11/11 → offline 66 用例评估（route 98.5%/grounding 100%/refusal 98.5%）→ 修复 E061-E066 乱码（原 git 版本即乱码） | 全链路 ✅ | 已完成 | `.codebuddy/memory/2026-08-12.md` |
| 2026-08-12 | 修复 12 项企业就绪度差距（Phase A/B/C 全部完成）：密钥清理、158 单测、CI、结构化日志、Repository、熔断缓存、FastAPI+认证限流、Docker/K8s、HNSW+BM25、注入防护+对抗用例+人工确认闸、审计轨迹、多轮会话+反馈 | ruff 0 错误 / pytest 158 passed / 13 commits | 已进入验证闭环 | `.codebuddy/memory/2026-08-12.md` |
| 2026-08-12 | 首次搭建 harness：生成 AGENTS.md / MEMORY.md / PROGRESS.md / DECISIONS.md / rules/（6 个）/ harness 辅助文件（3 个） | 生成完整性检查 | 已 commit（3a545fa） | `.codebuddy/memory/2026-08-12.md` |
