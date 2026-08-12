---
description: 全项目通用约束，语言/框架无关，始终生效
globs: "**/*.py"
alwaysApply: true
---
# 全局规则

> 本规则适用于所有 `**/*.py` 文件。
> 生效模式：始终生效

---

## 核心约束

1. **密钥零提交**：`.env`、API key、base_url 严禁出现在代码/注释/文档中；配置一律经 `src/utils/config.py` 从环境加载。why：密钥泄露即安全事件；when：任何时候；when_remove：永不。
2. **结构化输出走 pydantic**：工具返回与 Agent 输出必须由 `BaseModel.model_dump()` 产出，禁止散装 dict。why：UI/eval/CLI 三方消费，schema 是契约；when：新增返回结构时；when_remove：接口层重构完成时。
3. **数据锚点只增不改**：`data/kb_docs/`、`data/tickets.json` 的既有条目不得改语义，只能追加。why：它们是 eval 集与 demo 的锚点，改动会破坏评估基线；when：需要调整样例时；when_remove：接入真实后端时。
4. **日志统一 key=value**：所有日志用 `get_logger()`，格式 `key=value | key=value`。why：全链路可 grep 可观测（user_input/route_hints/tool_calls/response_summary）；when：任何新日志；when_remove：日志系统重构时。
5. **模块 docstring**：每个 `.py` 文件第一行必须有一句话 docstring 说明职责。why：demo 项目以可检视为第一要务；when：新建文件时；when_remove：永不。

## 代码风格

- Python 3.11+，`from __future__ import annotations`，全量类型注解（`def f(x: str) -> dict[str, str]`）
- 模块常量（关键词元组、hints）放文件顶部，用 SCREAMING_SNAKE
- 私有辅助函数用 `_` 前缀（如 `_resolve_route`、`_maybe_refuse`）
- 行宽 ~100 字符；函数内空行分段（如 main_agent.py 的 2 空行风格）

## 禁止模式

- 硬编码绝对路径 / API key / URL（参见 tech-traps 陷阱 2）
- `print()` 调试输出残留（应用入口 `main()` 的 CLI 打印除外）
- 对原始数据文件就地改写
- 提交 `data/eval_results/`、`__pycache__/`、`.venv/` 产物

## 推荐模式

- 分层调用：utils → tools → agents → app，禁止反向依赖（agents 不得 import evals）
- 新功能先写清楚输入/输出 schema（pydantic 模型），再实现逻辑
- 行为可解释：路由/拒答/澄清的规则尽量集中在可测试的纯函数中
