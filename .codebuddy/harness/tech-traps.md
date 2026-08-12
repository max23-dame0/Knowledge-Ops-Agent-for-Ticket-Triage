# 关键技术陷阱

> **角色**：[Cold] 冷记忆 — 仅在涉及对应技术时按需加载
> **来源**：项目实战踩坑记录 | **过期条件**：项目升级对应依赖版本后重新评估每条
> **使用**：每新增一条陷阱，追加到下方。格式：触发条件 + 错误做法 + 正确做法

---

## 1. 第三方提供商结构化输出不稳定

- **触发条件**：使用非官方 OpenAI 端点（本项目为 MiniMax），要求模型输出 JSON
- **错误做法**：直接 `json.loads(model_output)`，失败即报错
- **为什么错**：第三方 chat-completions 端点可能返回 Markdown 包裹、追加解释或部分字段缺失
- **正确做法**：`_coerce_agent_output` 兜底链——AgentAnswer 实例 → dict → 提取 JSON 对象 → 文本 regex fallback；每级失败降级下一级
- **检测方法**：regression 用例中观察 `pass_fail_summary` 中的解析类失败

## 2. 硬编码路径/密钥陷阱

- **触发条件**：代码中硬编码 `C:\Users\...`、`/Users/...` 绝对路径或 API key
- **错误做法**：`Path("/Users/me/knowledge-ops-agent/data/tickets.json")` 或把 key 写进常量
- **为什么错**：换机器/换环境即挂；密钥进 git 历史后即使删除也泄露
- **正确做法**：相对仓库根路径（`data/tickets.json`）+ `.env` 环境注入（见 global 规则）
- **检测方法**：review 时搜索 `C:\`、`/home/`、`/Users/` 前缀及 `sk-` 等 key 特征串

## 3. 工单 ID 变体归一化

- **触发条件**：用户输入 `tkt-1004`、`TKT1004`、`TKT 1004`、`TKT:1004`、裸数字 `1004`
- **错误做法**：直接字符串比较 `ticket_id == "TKT-1004"`
- **为什么错**：用户形态多样，直接比较必然漏匹配（README 演示了多种写法）
- **正确做法**：统一走 `normalize_ticket_id`（NFKC 归一化 + 正则提取），所有查询/比对共用
- **检测方法**：regression 用例 ticket_lowercase / ticket_compact / ticket_spaced / ticket_digits_only

## 4. rate limit（429）处理

- **触发条件**：MiniMax 端点并发/频率超限，报 429 / rate_limit
- **错误做法**：不重试直接让评估中断
- **为什么错**：离线评估批量跑时必然撞限流，整个跑批报废
- **正确做法**：`_run_agent_with_retry`（识别 429 → 指数退避重试 3 次）；评估单样本失败容忍继续
- **检测方法**：eval 输出 error 字段含 "429" 字样

## 5. 数据文件编码（BOM）

- **触发条件**：读取 `data/tickets.json` 等文件
- **错误做法**：`read_text(encoding="utf-8")` 不带 `-sig`
- **为什么错**：Windows 下文件常带 UTF-8 BOM，首字段解析出错（如 ticket_id 前多出 `\ufeff`）
- **正确做法**：`encoding="utf-8-sig"`（ticket_tools.py 已采用）
- **检测方法**：工单查询结果首条字段异常时检查 BOM

## 6. 文档变更后不重建 FAISS 索引

- **触发条件**：修改 `data/kb_docs/*.md` 后直接查询
- **错误做法**：只改文档不跑 `python -m src.rag.build_index`
- **为什么错**：检索读的是静态索引快照，文档改动不生效，grounding 评估失真
- **正确做法**：kb_docs 变更 → 重建索引 → 跑 regression 验证 KB 路径
- **检测方法**：检索结果不包含新文档内容时检查索引时间戳

---

<!-- 新陷阱追加于此，模板：
## N. {陷阱名称}

- **触发条件**：什么情况下会踩坑
- **错误做法**：错误的代码或操作
- **为什么错**：根因分析
- **正确做法**：正确的代码或操作
- **检测方法**：如何通过代码审查或工具检测
-->
