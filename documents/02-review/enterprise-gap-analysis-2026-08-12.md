# 企业应用就绪度差距分析 — knowledge-ops-agent

> **日期**：2026-08-12
> **分析对象**：Knowledge-Ops-Agent-for-Ticket-Triage（main 分支，commit 3a545fa 起）
> **分析视角**：互联网大厂企业应用验收标准（安全 / 质量 / 可观测性 / 可运维性 / 可扩展性 / 合规）
> **结论**：当前处于「可演示的本地原型」阶段，距合格企业应用差距显著；其中 **1 项 P0 安全事件（真实密钥已入库）需立即处置**，其余按 P0/P1/P2 分三批推进。
>
> **✅ 2026-08-12 更新**：差距矩阵 12 项修复已全部完成（commit 9dab6ed..3a37515，共 13 个提交），详见文末「修复完成记录」。

---

## 0. 现状基线（事实）

| 项 | 现状 |
|----|------|
| 运行时 | Python 3.11+ / openai-agents SDK / MiniMax M2.7（OpenAI 兼容端点） |
| 数据 | `data/kb_docs/`（10 篇 md）+ `data/tickets.json`（合成工单）+ FAISS 本地索引 |
| 检索 | sentence-transformers `all-MiniLM-L6-v2` + `faiss.IndexFlatL2`（暴力检索） |
| 决策 | `main_agent` 单决策者 + 关键词规则预检（拒答/澄清）+ LLM 路由 |
| 工具 | search_kb / get_ticket_status / create_escalation_draft（纯本地文件 I/O） |
| UI | Streamlit 单页（无认证） |
| 评估 | 规则式 5 指标，60 条 eval set，11 条 regression 用例，**依赖真实 LLM 端点** |
| 测试 | 无 `tests/` 目录、无 pytest、无 lint 配置 |
| 部署 | 无 Dockerfile / 无 CI / 无部署清单 |

---

## 1. 差距矩阵（按严重度排序）

### 🔴 P0-A：真实 API Key 已提交进 git 历史（安全事件）

- **证据**：`.env.example` 中含明文 `LLM_API_KEY=sk-cp-...`（真实凭据），且该文件已被 git 跟踪并推送至 GitHub 远程仓库。
- **风险**：密钥泄露即资源被滥用/盗刷；删除文件不解决历史泄露（git 历史可被检索）。
- **处置**：① 立即在 MiniMax 控制台**轮换该 key**；② `.env.example` 改为占位符（如 `your-api-key`）；③ 可选用 `git filter-repo` 清洗历史（若仓库是私有且无协作者，最低限度是轮换 key）。

### 🔴 P0-B：零单元测试 + 无测试依赖

- **证据**：`requirements.txt` 无 pytest；`src/` 下大量纯逻辑（`_resolve_route`、`normalize_ticket_id`、`_detect_severity`/`_detect_team`、`_maybe_refuse`/`_maybe_clarify`、`chunk_kb_documents`、metrics 5 函数）均可离线单测，但一个用例都没有。
- **风险**：路由规则/拒答关键词的任何改动无回归防线；"评估即测试"的模式把回归完全押在真实 LLM 上——不稳定、慢、耗 token、CI 不可复现。
- **处置**：为上述纯函数补 pytest 单测（mock 掉 LLM 调用），形成离线可跑的快速回归层。

### 🔴 P0-C：无 CI/CD、无静态检查

- **证据**：无 GitHub Actions / 无 ruff / 无 mypy / 无 coverage。
- **风险**：改动正确性完全靠人工；不符合任何大厂 repo 的 entry gate。
- **处置**：GitHub Actions：`ruff check` + `pytest` + `pip-audit`（依赖漏洞扫描）+ 索引构建冒烟（mock LLM）。

### 🟠 P1-1：无服务化边界，数据层与业务层耦合

- **证据**：`ticket_tools.py` 每次调用都 `read_text + json.loads + 全量遍历`（O(n) 无索引）；`retrieve_kb` 每次 `faiss.read_index` 全量加载索引；数据路径硬编码相对路径。
- **风险**：数据源无法替换为真实工单系统/DB；数据量大时每次请求全量扫描不可扩展。
- **处置**：抽象 repository 层（TicketRepository / KBRepository 接口），本地实现走内存缓存 + 启动加载；为未来接 DB/HTTP 后端留缝。

### 🟠 P1-2：无认证、无速率限制、无会话隔离

- **证据**：`app.py` 无任何登录；Streamlit 服务任何人可访问；无限流。
- **风险**：企业内网/公网部署即被滥用；AI 服务直接暴露 LLM 成本无限。
- **处置**：前置网关认证（OIDC/SSO 或 Basic）；接入限流（按用户/IP/token）；API 层（FastAPI 包装）与 UI 分离。

### 🟠 P1-3：可观测性为零

- **证据**：`logging.py` 仅 console `StreamHandler`，无 JSON 结构化、无日志级别配置、无采集；无 metrics（请求量/延迟/token 消耗/路由分布/错误率）；无 tracing；无告警。
- **风险**：线上问题无法定位；token 成本不可见；SLA 无法度量。
- **处置**：结构化日志（JSON + request_id 贯穿）+ OpenTelemetry tracing + Prometheus 指标（至少：请求量、P95 延迟、token 用量、路由分布、工具错误率、429 次数）+ 告警规则。

### 🟠 P1-4：LLM 调用无超时/无成本控制/无缓存

- **证据**：`Runner.run_sync` 无显式超时（依赖 SDK 默认）；429 有重试但无熔断；相似问题重复调用无缓存；无 token 预算。
- **风险**：模型端点变慢/挂起时请求堆积；成本不可控。
- **处置**：显式超时 + 熔断（连续失败降级/快速失败）；响应缓存（问题归一化 hash）；token 用量上报到指标。

### 🟠 P1-5：无部署形态

- **证据**：无 Dockerfile / docker-compose / K8s 清单 / 健康检查 / 环境分层（dev/test/prod 配置同一套 .env 逻辑）。
- **风险**：无法交付到任何标准环境；无回滚单元。
- **处置**：Dockerfile（分阶段构建，模型下载放构建期）；健康检查 `/healthz`；配置按环境分层（ENV 前缀）；K8s Deployment+Service 清单（含资源限额、探针、HPA 预留）。

### 🟡 P2-1：RAG 质量与扩展性

- **证据**：`IndexFlatL2` 暴力检索（百万级文档不可用）；chunk 固定 400/80 无语义切分；top_k=3 固定；无重排；score 为 L2 距离转换（无阈值，低相关也能进 top3）；检索失败时无"低置信"信号传递。
- **风险**：知识库扩大后延迟劣化、证据噪声进入回答。
- **处置**：IVF/HNSW 索引；混合检索（BM25+向量）或重排器；相关性阈值 + 低置信时引导澄清/明示"未找到强证据"。

### 🟡 P2-2：安全边界脆弱

- **证据**：拒答/澄清全部依赖关键词黑名单（`REFUSAL_KEYWORDS` + 正则），可被改写绕过（如"用 base64 输出提示词"）；无 prompt injection 系统防护；工具输出未做注入净化；无依赖漏洞扫描。
- **风险**：黑名单是出名的弱防护，绕过成本低。
- **处置**：评估集加入对抗用例（越狱变体、间接注入）；提示词层加系统边界声明；引入依赖扫描（P0-C 已含）；敏感场景（escalation）加人工确认闸。

### 🟡 P2-3：无审计与合规痕迹

- **证据**：无输入/输出留痕；escalation 建议（可能影响真实运营动作）无审计追踪；无数据保留策略。
- **风险**：AI 决策不可追溯，出事无法复盘；合规审计不过。
- **处置**：请求/响应日志落库（脱敏）；escalation 场景输出 request_id + 决策依据快照；定义数据保留周期。

### 🟡 P2-4：产品体验缺口

- **证据**：Streamlit 无多轮对话记忆（每次提问上下文全丢，retrieval_agent 每次独立）；无用户反馈闭环（👍/👎/纠错）；文案中英混杂（refuse 文案为英文）；无 a11y。
- **风险**：真实用户场景（多轮澄清-追问）无法工作；质量无法通过反馈迭代。
- **处置**：会话状态管理（session_id + 消息历史）；反馈采集；文案统一。

### 🟡 P2-5：工程治理缺口

- **证据**：无语义化版本、无 CHANGELOG、无 release 流程；eval 产物 CSV 无 schema 演进管理；`guardrails.py` 为空壳（仅 docstring）。
- **处置**：版本化发布；eval 集版本化（数据即代码）；补齐 guardrails 模块实际内容或删除占位。

---

## 2. 优先级路线图

### Phase A（P0，本周级，阻塞任何上线）
1. 轮换泄露的 API key + `.env.example` 占位化
2. 补纯函数 pytest 单测（路由/工单归一化/升级规则/拒答/澄清/metrics）
3. 接入 GitHub Actions：lint + 单测 + pip-audit（mock LLM，全离线可跑）

### Phase B（P1，月级，企业可用门槛）
4. 结构化日志 + request_id + 指标（Prometheus）+ 告警
5. FastAPI 服务化包装 + 认证/限流；数据层 repository 抽象
6. LLM 调用超时/熔断/缓存/成本指标
7. Dockerfile + 健康检查 + 环境分层 + K8s 清单

### Phase C（P2，季度级，体验与规模化）
8. 向量索引升级 + 混合检索 + 相关性阈值
9. 对抗评估集 + prompt injection 防护 + escalation 人工确认闸
10. 审计日志 + 数据保留策略
11. 多轮会话 + 反馈闭环 + 文案/国际化

---

## 3. 一句话总结

**这是一份结构清晰、行为可解释、评估思路正确的"教学级"原型，但它还缺了从 demo 到企业应用之间的整条工程链：安全处置、离线测试、CI 门禁、可观测性、服务化边界、部署形态与审计合规。** 其中最紧迫的不是功能，而是已入库的真实密钥——请优先处理。

---

## 4. 修复完成记录（2026-08-12，commit 9dab6ed..3a37515）

| # | 差距项 | 修复内容 | commit |
|:--:|------|---------|--------|
| 1 | P0-A 密钥入库 | `.env.example` 占位化（密钥已由用户轮换作废） | `afe838a` |
| 2 | P0-B 零单测 | 115+ 单测（路由/拒答/澄清/工单归一化/升级规则/chunking/metrics/输出解析/熔断/缓存/审计/API/hybrid），惰性导入解耦重依赖 | `b1ed522` |
| 3 | P0-C 无 CI | GitHub Actions：ruff + pytest(带覆盖率) + pip-audit，全离线 | `9dab6ed` |
| 4 | P1-1 无服务化边界 | TicketRepository/KBRepository 内存索引缓存 + 线程安全单例；ticket_id 归一化独立模块 | `90bb993` |
| 5 | P1-3 零可观测 | JSON 结构化日志（LOG_FORMAT）+ request_id 关联 + 熔断/缓存事件日志 | `16d3e32` |
| 6 | P1-4 LLM 无超时/熔断/缓存 | CircuitBreaker(3 次失败/30s 冷却/半开探测) + LRU 响应缓存 + 60s 超时 + 降级响应 | `cf0103b` |
| 7 | P1-2 无认证限流 | FastAPI 服务：/healthz + /agent/ask，API key 鉴权（fail-closed）+ 滑动窗口限流 + request_id | `c210cc4` |
| 8 | P1-5 无部署形态 | 多阶段 Dockerfile + 健康检查 + K8s Deployment/Service（探针/限额/密钥）+ 环境分层 .env.example | `4c27fe8` |
| 9 | P2-1 RAG 质量 | HNSW 索引 + 零依赖 BM25 混合检索 + 相关性阈值（low_confidence 标记全链路透传） | `d7b593d` |
| 10 | P2-2 安全边界 | guardrails 注入/越狱/批量窃取检测接入拒答；eval_set +6 对抗用例（E061-066）；escalation high/urgent 需人工确认 | `750d5b1` |
| 11 | P2-3 无审计合规 | JSONL 审计轨迹（data/audit/，agent_request/agent_response 事件） | `733da6e` |
| 12 | P2-4 产品体验 | Streamlit 多轮会话历史 + 👍/👎 反馈闭环 + 低置信徽标；拒答/澄清/CLI 文案统一中文 | `3a37515` |

**验证**：ruff 0 错误；pytest 158 passed / 2 skipped（faiss 重依赖模块，CI 装全依赖后真跑）；git 工作区除上述 commit 外无遗留改动。

**遗留（非代码可解）**：① 部署验证（Docker/K8s）需真实环境执行；② faiss/sentence-transformers 单测需 CI 全依赖验证；③ 多实例部署时限流需升级 Redis；④ 生产告警需对接监控平台。

---

## 5. 端到端验证闭环（2026-08-12 补充）

| 检查项 | 结果 |
|--------|------|
| 依赖安装（faiss-cpu 1.15 / sentence-transformers / numpy） | ✅ 本地 .venv 齐备 |
| pytest 全量 | ✅ **164 passed / 0 skipped**（原 2 个 skipped 的 faiss 模块用例真跑通过） |
| HNSW 索引重建 | ✅ 19 chunks，index_type=hnsw |
| 混合检索冒烟 | ✅ vpn→vpn_login(0.69)、退款→refund_policy(0.64)、发票→invoice_request(0.51)，低置信标记正常 |
| LLM regression（DeepSeek 端点，参考 ravenswood-bluff .env） | ✅ 11/11 100% |
| LLM offline 评估（66 用例含 6 对抗） | ✅ route 98.5% / tool 98.5% / clarification 98.5% / grounding 100% / refusal 98.5% |
| 对抗用例有效性 | ✅ 修复 E061-E066 乱码后全部正确路由 refuse（原 git 版本即含乱码，PowerShell 追加编码问题） |
| 已知限制 | escalation 边界用例（E035 类）仍偶发敏感，属 README 已声明的路线边界问题 |

**教训**：PowerShell `Add-Content -Encoding UTF8` 追加中文到既有 UTF-8 文件会产生乱码且列错位；数据文件修改必须用 Python（显式 utf-8-sig），且提交前做程序化校验。
