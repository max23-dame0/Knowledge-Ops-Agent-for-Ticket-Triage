# 从"缝合的演示系统"到"真正的 Agent"——评测一体化与去规则化重构报告

> 日期:2026-08-17
> 范围:knowledge-ops-agent(ticket triage 支持 Agent)
> 动机:项目当前存在两个相互强化的结构性问题:(1) 评测与项目本身分离,evidence 不能复现;(2) 数百行硬规则关键词堆叠替代了 LLM 决策,agent 名不副实。

---

## 0. 结论摘要

| 问题 | 病根 | 一句话方案 |
|---|---|---|
| 评测与项目分离 | 所有评测调 `run_agent`(真实 LLM),结果是一次性的、不可复现的;离线数据集与在线服务无共享机制 | Golden-set CI 双模式 + **决策回放语料库(replay corpus)** 作为唯一真相源 |
| 规则堆叠的"假 Agent" | 路由在规则层和 LLM 之间双重决策,7 层 if/elif 以 unicode 转义硬编码 700+ 行,`retrieval_agent` 是不含 LLM 的纯函数包装 | 五层控制金字塔:单一 Guardrail(硬安全)→ 显式可评估的路由函数 → 预算化检索编排 → LLM 决策 → 评估元数据独立 |


### 五层控制金字塔(目标架构)

| 层 | 裁决权 | 实现 | 证据 | 可评估性 |
|---|---|:---:|---|---|
| L1 硬安全闸 | 唯一可确定性拒绝 | 注入检测、密钥、越权导出 | 规则(保留,但收敛为一处) | 确定,100% 离线 |
| L2 路由函数 | 唯一可确定性路由 | `route()` 显式函数,返回 `(route, confidence, needs_clarify, reasons)` | 轻量分类器或检索证据(禁用脆词典) | 确定,100% 离线 |
| L3 检索编排 | 唯一工具调用预算 | `budget plan`:`(kb, top_k=3, budget=1) → (escalation, draft)` | 预算协议 | 确定 |
| L4 LLM 决策 | 证据之上的唯一答案裁决 | 工具调用 + 证据引用 + 最终 JSON | 工具结果 + 引文 + 轨迹 | 半确定,靠回放 |
| L5 评估元数据 | 只读评分 | registry + labelbox + 统一指标 | 同 L2/L4 证据 | 确定 |

**铁律**:每个决策要么由 L1/L2 确定性产生(离线可复现),要么由 L4 产生且只消耗 L3 批准的预算;两处都不产生决策则默认 `clarify`。

---

## 1. 诊断:两个问题的本质与共同病根

### 1.1 问题一:评测与项目是"两座孤岛"

**事实**:
- `src/evals/run_evals.py`(526 行)、`external_bench.py`(234 行)、`ticket_bench/`(~1100 行)全部通过 `run_agent()` 调用真实 LLM;
- 输出落到 `data/eval_results/`(gitignore),带时间戳的 30+ 个文件不可重放、不可复现;
- `data/eval_results/final_report_20260817_1030.md` 中"全量 18537 条"的最终结论因后端 502 而有 60% 数据无效——**报告的价值完全依赖当时那台机器、那个模型、那次网络**;
- 外部数据集(clinc_oos、JailbreakBench、Tobi 20k)与内部 `eval_set.csv` 在代码、目录、指标上互不相通。

**本质**:评测链路的输入(问题)→ 中间产物(模型决策、工具调用)→ 输出(结论)三者中,只有输出被持久化,且无法与任意新版本代码重放对比。

**后果**:如果简历面试中被问"你的 route_accuracy 98.5% 怎么复现",你将无话可说——这是比"项目是 demo"更严重的问题。

### 1.2 问题二:这不是 Agent,是"规则堆 + LLM 打补丁"

**事实**:
- `main_agent.py` 1065 行,其中约 700 行是规则:`_resolve_route` / `_maybe_refuse` / `_maybe_clarify` / `_looks_like_*` 等 7 层 if/elif,加上 5 个关键词元组(KB_KEYWORDS、ESCALATION_HINTS、REFUSAL_KEYWORDS……),大量 `\u5de5\u5355` 形式的硬编码;
- 路由决策在规则层和 LLM prompt 之间**双重进行**——规则层先裁决,LLM 再被 17 条 prompt 规则要求重判一遍,冲突面靠 prompt 协商;
- `retrieval_agent` 是无 LLM 的纯函数包装(65 行),只是 `search_kb` + 字段归一化,不具备任何 agent 职责;
- 每次 eval 失败 → 加一条关键词/一条 if,属于典型的 brittle hardcoding 循环。

**本质**:LLM 在这个系统中不是"决策者",而是"规则引擎缝隙里的补丁"。这可以是一个能工作的 demo,但不能称为 agent 架构。

### 1.3 共同病根:决策证据链没有结构

路由规则、guardrail 规则、检索结果、LLM 输出、评估指标,五者各自为政,没有统一的"决策 + 证据"数据契约。因此:
- 无法离线重放 LLM 决策(评测孤岛);
- 只能靠更多规则去纠正错误(规则堆叠);
- 无法回答"这个行为为什么发生"(不可解释)。

**重构要解决的是同一件事:让每一次决策都携带可持久化、可回放、可评估的证据。**

---

## 2. 方案 A:把评测做成项目的一等公民(五件套)

### A1. Golden-set CI 双模式(评测进 CI,离线可跑)

将 `eval_set.csv` + 回归集合并为 **golden set**(route/tool/clarify/refuse/grounding 标签),在 CI 中分两档跑:

```
make eval-smoke    # 12 条回归,< 60s,要求 100%,每次 PR 必跑
make eval-full     # 全量 golden set,nightly,记录趋势曲线
```

**关键点**:
- `eval-smoke` 必须**离线可跑**(L1/L2 确定性 + mock 工具),不依赖 LLM key——彻底解决"评测需要密钥所以 CI 跑不了"的问题;
- `eval-full` 需要 LLM,但通过 A2 的 cache 避免重算(见下);
- 评测结果进入 PR 评论/CI artifact,不再只存在本地 `data/eval_results/`。

### A2. 决策回放语料库(Replay Corpus)——决定性的一步

**目标**:让"LLM 决策"变成可持久化、可 diff、可复现的资产。

```
data/replay/
├── samples.jsonl        # 黄金决策轨迹(人工审核通过)
└── sessions/<run_id>.jsonl  # 每次评测的完整轨迹
```

每行一条决策记录,统一数据契约:

```json
{
  "run_id": "ci-20260817-abc",
  "sample_id": "E025",
  "input": {"question": "客户连续两天无法登录而且影响多个用户 是否应该升级处理"},
  "stage": "decision",
  "trace": {
    "guardrail": {"action": "pass", "rules_hit": []},
    "route_fn": {"route": "escalation", "confidence": 0.82, "needs_clarify": false,
                 "reasons": ["strong_signal:多个用户"], "matched": ["escalation_signal"]},
    "plan": {"steps": [{"tool": "create_escalation_draft", "budget": 1}]},
    "llm": {"raw": "{...}", "tool_calls": [{"tool": "create_escalation_draft", "args": {...}}],
            "final_json": "{...}", "tokens": {"in": 412, "out": 89}, "latency_ms": 1200},
    "final": {"route": "escalation", "answer": "...", "evidence": ["..."], "confidence": 0.85}
  },
  "label": {"expected_route": "escalation", "should_clarify": false,
            "should_use_tool": true, "expected_tool": "create_escalation_draft",
            "unsafe": false},
  "scores": {"route_ok": true, "tool_ok": true, "grounding_ok": true},
  "approved": true
}
```

**它的三个用途,让评测与项目彻底结合**:

1. **离线重放**:测试中直接注入 `trace.llm`(mock 掉 LLM),断言"代码变化后,同一决策是否保持一致"——这就是"离线评估"的真正含义,替代现在每次跑真 LLM 的做法;
2. **变更 diff**:每次 PR 跑 eval 后,新旧轨迹 diff 出"哪些样本的 route/tool/evidence 变了",变化的样本成为 code review 的焦点——评测直接驱动开发;
3. **LLM-as-judge 的语料**:未来做 judge 时,judge 直接消费 replay 里的 `final` vs `label`,不需要重跑模型。

### A3. live-offline 双向循环:生产行为回流为测试样本

**方向一(offline→live)**:部署前必须通过 `eval-smoke`;CI artifact 与镜像 tag 绑定,无法追溯评测结果的镜像不可部署。

**方向二(live→offline,把生产与测试连通)**:
- 服务的审计轨迹(`data/audit/*.jsonl`)+ `tool_calls` 已是现成原料;
- 新增一个导入命令:`python -m src.evals.ingest --from audit --label-dir documents/labelbox`,将生产请求变成待标注样本;
- 每周从生产导入 N 条(覆盖低置信、tool 失败、refusal、human_handoff 四类),人工标注后**进入 golden set**,形成"生产 → 评测集 → 优化 → 部署"闭环。

这直接解决现在"eval 集只有 67 条且由作者手写"的样本偏置问题。

### A4. CI 成本护栏(使 LLM 评测可长期持续)

- 所有 LLM 评测走 cache(按 `question + model + commit` 键控),未命中才调用;
- `eval-full` 设置预算上限(如 `MAX_EVAL_TOKENS`),超限自动降级为 `eval-smoke` 并告警;
- 现在 `_run_agent_with_retry` 里的 429 重试逻辑应提升为统一的 `EvalRunner` 组件,带背压与熔断(复用 `src/utils/resilience.py`)。

### A5. 统一 eval registry:内部/外部/benchmark 数据集一个入口

```
src/evals/registry.py
DATASETS = {
  "golden":      {"loader": csv,   "task": "route/tool/clarify/refuse", "cost": "offline"},
  "injection":   {"loader": hf,    "task": "guardrail",                "cost": "offline"},
  "oos":         {"loader": hf,    "task": "oos_detection",            "cost": "offline"},
  "tobi_tickets":{"loader": hf,    "task": "route/grounding",          "cost": "llm"},
  "itsm":        {"loader": hf,    "task": "route",                    "cost": "llm"},
}
```

每个数据集声明自己的 task 类型与成本档位;`make eval-*` 按档位调度。现在散落的 `external_bench.py` / `ticket_bench/` 全部收敛为 registry 下的 loader + metric。

---

## 3. 方案 B:去规则化,把 Agent 做成真正的 Agent

### B1. 把"路由"变成显式的、可评估的函数(证据链统一的关键)

路由不再藏在 if/elif 堆里,而是返回结构化决策 + 证据:

```python
class RouteDecision(BaseModel):
    route: Literal["kb", "ticket", "escalation", "clarify", "refuse"]
    confidence: float
    needs_clarify: bool
    reasons: list[str]          # 人类可读,如 "escalation_signal:多个用户"
    matched: list[str]          # 命中的信号 id,直接进入 replay 与评估
```

- **轻量路由方案(推荐先行)**:用 LLM 一次性输出 route 决策(温度 0),路由 prompt 只写"分类指令"不写"行为规则";
- **确定性路由方案(更稳、离线可评)**:训练/使用一个轻量文本分类器(logistic/小模型),`reasons` 来自特征命中——然后 L1 判定与分类器输出全部离线可测,CI 不需要 LLM;
- 路由正确性由 golden set 直接回归,新增行为只需加标注样本,**删除所有关键词元组**。

### B2. 把所有规则收敛为"一个 Guardrail 策略"(而非 7 层 if/elif)

规则只保留真正不可交给模型的硬安全项,且收敛为一处:

```python
GUARDRAILS = [
  {id: "g_injection",       check: looks_like_injection_attack,  action: "refuse", hard: true},
  {id: "g_bulk_data",       check: ...,                          action: "refuse", hard: true},
  {id: "g_system_exfil",    check: ...,                          action: "refuse", hard: true},
  {id: "g_missing_ticket",  check: ...,                          action: "clarify", hard: false},  # 交给 LLM 最终定夺
]
```

- `hard=true`:规则直接定案(refuse),LLM 无权推翻;这是唯一合理的确定性层;
- `hard=false`:规则只是**提示**,最终裁决在 LLM——消除双重决策;
- 每个 guardrail 有 id,进入 replay 的 `trace.guardrail.rules_hit`,离线可测。

**现存的 `_maybe_clarify` 里约 10 个分支**(账号问题/billing 的事/单子有没有进展……)几乎全部删除——它们要么是路由决策(交给 B1),要么是 prompt 里的行为规范(交给 B5),用"裸关键词判 clarify"既不可解释也不可维护。

### B3. 用检索证据替换词典匹配

- **政策类**(SLA、升级政策、退款政策)已经天然在 KB 里——把 `KB_POLICY_HINTS`、`ESCALATION_POLICY_HINTS` 词典删掉,让"这是政策问题还是个案"由 L4 依据检索证据判断,`kb` 路由自然覆盖;
- **ticket_id 识别**是个真正的确定性功能,保留在 `normalize_ticket_id`(它有 100% 测试覆盖),但"这是不是一个 ticket 查询"交给路由函数,而不是 TICKET_HINTS 词典;
- **升级严重性**:`escalation_tools._detect_severity` 的 urgent/high/medium 词典是有业务价值的(可解释、可审计),保留但改造成**证据之一**:把词典命中的信号注入 LLM 的 upgrade draft,让 LLM 做最终严重性决策,词典只做解释。`needs_human_confirmation`(high/urgent)保留——这是硬安全。

### B4. 预算化检索编排:agent 化的核心体验

现在 LLM 可以自由选 3 个工具,没有任何代价约束。增加一个轻量预算协议:

```python
Plan = [(tool="search_kb", budget=1), (tool="create_escalation_draft", budget=1)]
```

- 路由为 `escalation` 且 strong signal → 计划直接是 escalation draft(现状已用 prompt 打了这个补丁,改为显式计划);
- 工具预算耗尽后 LLM 必须给出结论或 `clarify`——消灭"LLM 反复检索不出结论"的空转;
- 预算本身进入 replay(`trace.plan`),评测可断言"该场景只消耗了多少预算"。

### B5. Prompt 与评估元数据分离(结构化评估的底座)

把现在 17 条行为规则的主 prompt 拆成**契约**,用代码保证,而非文本祈祷:

```python
class AgentContract:
    tool_names: tuple       # 可用工具
    output_schema: type     # pydantic 模型(LLM 结构化输出)
    budget: int             # 工具预算上限
    evidence_required: bool # 每条结论必须有证据字段
    behavior_rules: tuple   # 只保留必须的、可被评测验证的行为规则
```

- 输出 schema 直接走 `openai-agents` 的 structured output / JSON 模式,把现在 `_coerce_agent_output` 里的 `_strip_think_blocks` + `_extract_json_object` + `_parse_text_response` 三层容错降级为**一层**兜底(第三方 provider 波动时的防御),而不是默认路径;
- "规则是否被遵守"由评测度量(L2/L5),而不是 prompt 祈祷——这是"真 agent"与"prompt 规则引擎"的分水岭。

### B6. `retrieval_agent` 改名并赋予真实职责

现状它是纯函数包装,却占了"agent"之名。改为 `retrieval_grader`(或直接模块化进 L3):

- 职责 = 检索 + 证据质量分级(如 `low_confidence` 过滤、引文格式、冗余去重);
- 明确它不是 agent,消除 README 中"受控子 agent"造成的架构误导;
- 这一步也是简历上的诚实加分项:"我发现模块名与职责不符并修正了它"。

---

## 4. 实施路线图(三阶段,每阶段有退出准则)

### 阶段 1:证据链 + 回放语料(1-2 周)

| 任务 | 交付物 | 退出准则 |
|---|---|---|
| RouteDecision / AgentContract 模型 | `src/agents/contracts.py` | 类型 + 单测 |
| Guardrail 策略表(硬/软) | `src/agents/guardrails.py` v2 | 现有 171 测试全部通过,硬规则不变 |
| `trace()` 装饰器记录完整决策轨迹 | `src/agents/trace.py` | 每个决策路径都产出 trace |
| replay 语料 + 离线重放 runner | `data/replay/` + `src/evals/replay_runner.py` | `eval-smoke` 在无 key 环境 100% 通过 |
| golden set 合并 + CI 双模式 | `Makefile` + `.github/workflows/ci.yml` 更新 | PR CI 跑 eval-smoke,本地可复现 |

**关键动作**:阶段 1 不做任何行为改动——先把现有行为"冻结"进 replay,建立可对比的基线。这是安全网。

### 阶段 2:去规则化(2-3 周)

| 任务 | 交付物 | 退出准则 |
|---|---|---|
| 路由函数化,删除全部关键词元组 | `route_fn` + golden set 驱动 | route_accuracy 不降,且路由可离线评估 |
| 删除 `_maybe_clarify` 的 10 个词典分支 | 逻辑删除 diff | clarify 样本行为不变(靠 replay 对比) |
| 政策类查询走 KB 证据 | 删除 POLICY_HINTS | E008/E009 及新增政策样本通过 |
| 检索预算协议 | `plan` 注入 | escalation 场景预算断言通过 |
| retrieval_agent → retrieval_grader 重命名 | 重命名 + 文档 | 命名与职责一致 |

**每一步都用 replay diff 验证**:"删除这条规则,哪些样本的行为变化了?"——变化的必须逐条解释。

### 阶段 3:评估生态闭环(2 周+)

| 任务 | 交付物 | 退出准则 |
|---|---|---|
| 生产审计导入标注工具 | `src/evals/ingest.py` | 一条真实请求 → 标注 → golden set 全流程可用 |
| eval registry 统一 5 个数据集 | `src/evals/registry.py` | `make eval-full` 一个入口跑全部 |
| 成本护栏 | EvalRunner + cache | eval-full 预算内运行 |
| LLM-as-judge(可选,基于 replay) | judge 消费 replay | 达到上次实验未达的 85% 一致性再启用 |

---

## 5. 衡量成功的指标(新增)

| 指标 | 现状 | 目标 | 定义 |
|---|---|---|---|
| replay 覆盖率 | 0% | 100% | 有决策轨迹的 golden 样本占比 |
| 离线可评估率 | ~0% | ≥95% | 不依赖 LLM key 可断言的样本占比 |
| 路由规则行数 | ~700 | <80 | 硬规则只做安全闸与 ID 解析 |
| golden set 规模 | 67 | 200+(含生产导入) | 覆盖 5 路由 + 边界 + 对抗 |
| eval 复现率 | 0 | 100% | 同一 commit 两次 eval 结果可 diff 对比 |

---

## 6. 风险与反模式

| 风险 | 对策 |
|---|---|
| 删除规则后模型路由漂移 | 先冻结 replay 再动刀,每次删除用 diff 验证;温度保持 0 |
| 完全去规则导致线上失控 | 只去"决策规则",**硬安全闸(L1)永不交给模型**;`needs_human_confirmation` 保留 |
| replay 成为新负担 | 只 golden set 保存黄金轨迹;普通运行轨迹按 run_id 清理 |
| 引入 LLM judge 后指标幻觉 | 沿用现有校准纪律:一致性 <85% 不启用,报告负面结果 |
| 用重排/rerank 掩盖检索问题 | 预算化编排优先于模型加码;检索质量先看 recall@k(已有 C4 基线) |

---

## 7. 这对简历叙事意味着什么

**重构前能讲的**:会拼 RAG + Agent SDK + FastAPI 的"全栈 demo"。

**重构后能讲的**:

1. "我把评测从'跑一次真模型'重构成了**可回放的决策语料库**,PR 能 diff 出每次改动对 200 个样本的决策影响" —— 这是应届生简历里极罕见的工程能力;
2. "我识别出 700 行规则与 LLM 的双重决策冲突,把系统重构为 Guardrail / 路由 / 检索 / 决策 / 评估五层控制金字塔,硬规则收敛到安全闸,行为正确性交给可评估的路由函数和 LLM" —— 架构判断力;
3. "我用决策证据链统一了生产审计与评测集,生产请求可回流为标注样本" —— 数据闭环思维;
4. 加上原有的"LLM judge 校准失败而拒绝启用"的负面实验报告 —— 方法论。

**一句话**:把"我会用工具"升级为"我能为不可靠的系统建立可靠性工程"——这才是简历分水岭。

---

## 附:核心文件对照

| 现文件 | 目标归属 |
|---|---|
| `main_agent.py`(1065 行) | 拆为 `contracts.py` / `route_fn.py` / `guardrails.py` v2 / `trace.py` / `main_agent.py`(核心 <300 行) |
| `retrieval_agent.py`(65 行) | → `retrieval_grader.py`(检索 + 证据分级) |
| `run_evals.py`(526 行) | → `registry.py` + `replay_runner.py` + 薄 CLI |
| `external_bench.py` / `ticket_bench/` | → registry 下的 loader + metric |
| `data/eval_results/*.csv`(30+ 文件) | → `data/replay/` 结构化轨迹 + 黄金集 |
| `eval_set.csv`(67 条) | → golden set(200+,含生产导入) |
