---
description: src/agents 主决策层与证据层规则
globs: "**/agents/**"
alwaysApply: false
---
# agents 层规则

> 本规则适用于 `**/agents/**` 匹配的文件（main_agent.py / retrieval_agent.py / guardrails.py）。
> 生效模式：涉及 agents 模块时加载

---

## 核心约束

1. **单决策 owner**：顶层路由（kb/ticket/escalation/clarify/refuse）只能由 `main_agent` 决定；`retrieval_agent` 只做检索证据规范化，不得拥有路由/决策逻辑。why：架构决策 D004；when：修改 agent 职责时；when_remove：D004 变更时。
2. **输出必须走 `_finalize_response` 规范化**：route 归一化（clarification→clarify、refusal→refuse）、兼容别名填充（next_actions/should_handoff）。why：UI/eval 依赖稳定字段；when：任何返回路径；when_remove：接口层重构时。
3. **模型输出必须容忍**：`_coerce_agent_output` 兜底链路（AgentAnswer → dict → JSON 提取 → 文本 regex）不得移除。why：第三方提供商结构化输出不稳定（tech-traps）；when：修改输出解析时；when_remove：模型保证 schema 时。
4. **预检顺序固定**：`_maybe_refuse` → `_maybe_clarify` → LLM 运行，不得交换。why：安全拒答优先于一切；when：改 run_agent 流程时；when_remove：规则层重构时。
5. **关键词规则与提示词同步**：修改 `MAIN_AGENT_INSTRUCTIONS` 时必须同步检查 hints 元组（KB_KEYWORDS/TICKET_HINTS/ESCALATION_HINTS/REFUSAL_KEYWORDS 等）。why：规则层与提示词双轨，不同步会互相打架；when：任何路由逻辑变更；when_remove：双轨制废弃时。

## 代码风格

- 路由判定用独立纯函数（`_looks_like_*` / `_has_strong_escalation_signal`），布尔化、可单测
- 关键词元组用常量集中管理，禁止散落魔法字符串
- 日志行格式：`route_hints=... | ticket_id:... | will_call_*:...`，保留下游可观测

## 禁止模式

- 在 main_agent 之外 import 并调用 `run_agent` 做递归决策（app.py 的 UI 展示除外）
- 移除兼容别名字段（next_actions/should_handoff/needs_clarification）——旧调用方仍在使用
- 在指令中鼓励模型输出 `<think>` 或推理过程

## 推荐模式

- 新路由边界先写纯函数 + 用例，再接入 run_agent
- 拒答/澄清文案保持简短中文一句话（对照 `_maybe_refuse` / `_maybe_clarify` 现有风格）
