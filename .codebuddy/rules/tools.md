---
description: src/tools 工具层规则
globs: "**/tools/**"
alwaysApply: false
---
# tools 层规则

> 本规则适用于 `**/tools/**` 匹配的文件（kb_search.py / ticket_tools.py / escalation_tools.py）。
> 生效模式：涉及工具层时加载

---

## 核心约束

1. **返回契约 = pydantic schema**：每个工具的输出必须由对应 `BaseModel.model_dump()` 产出（TicketLookupResponse / EscalationDraft 等），字段名不得随意改。why：`main_agent._record_tool_call` 与 UI 证据渲染依赖字段名；when：改工具输出时；when_remove：契约重构时。
2. **ticket_id 归一化唯一入口**：所有工单解析必须走 `normalize_ticket_id`（接受 TKT-1004 / TKT1004 / TKT 1004 / 裸数字等变体）。why：用户输入形态多，归一化保证匹配一致；when：任何工单查询；when_remove：永不。
3. **找不到 = 结构化错误，不是异常**：工单未找到/数据文件缺失时返回 `found=False + error` 字段，禁止抛异常。why：agent 需要基于错误信息生成下一步动作（指令第 12 条）；when：任何查找路径；when_remove：永不。
4. **severity/team 枚举固定**：severity ∈ {urgent, high, medium, low}，suggested_team ∈ {l2_network, billing_ops, account_support, platform_support}，新增级别需同时更新文档与测试。why：UI 与评估依赖枚举稳定；when：扩展规则时；when_remove：规则引擎重写时。
5. **规则式逻辑集中在纯函数**：`_detect_severity` / `_detect_team` 保持无状态关键词匹配，方便单测。why：升级建议是 demo 核心卖点，规则透明可解释；when：改判定逻辑时；when_remove：接入真实后端时。

## 代码风格

- 工具函数命名动词开头（get_/create_/search_/normalize_）
- 数据文件读取用 `Path("data/...")` 相对路径 + utf-8-sig 编码（tickets.json 有 BOM）
- 关键词元组常量放文件顶部

## 禁止模式

- 在工具层做路由决策或引用 agents 模块
- 抛异常表达"业务未找到"（只允许 IO/编程错误）
- 修改 `data/tickets.json` 以迎合查询结果

## 推荐模式

- 新工具先定义输出 schema 再写实现，schema 即文档
- 返回 dict 时保留原始字段名，兼容旧调用方（参考 get_ticket_status 的 found/error 风格）
