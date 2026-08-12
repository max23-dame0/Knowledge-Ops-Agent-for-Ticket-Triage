---
description: src/utils 基础设施规则
globs: "**/utils/**"
alwaysApply: false
---
# utils 层规则

> 本规则适用于 `**/utils/**` 匹配的文件（config.py / logging.py）。
> 生效模式：涉及基础设施时加载

---

## 核心约束

1. **配置只从环境加载**：`get_openai_settings()` 是唯一配置入口，从 `.env` / 环境变量读取 LLM_MODEL_ID / LLM_API_KEY / LLM_BASE_URL，key 缺失时必须报清晰错误（带修复提示）。why：README §7 明确"API key 缺失则清晰退出"；when：任何配置读取；when_remove：配置方案变更时。
2. **日志格式标准统一**：`get_logger("knowledge_ops.xxx")` 命名空间按模块，日志内容 `key=value` 风格。why：main_agent 全链路日志依赖此格式被 grep；when：任何日志；when_remove：日志系统重构时。
3. **不存业务状态**：utils 层不得缓存会话级状态（如 `_CURRENT_TOOL_CALLS` 这类属于 agents 层）。why：基础设施保持无状态可复用；when：新增 util 时；when_remove：永不。

## 代码风格

- 类型注解完整；配置类用 dataclass 或简单 dict
- 日志等级：info（流程节点）/ warning（可恢复异常）/ error（失败）
- 不做魔法值隐藏：环境变量名集中定义常量

## 禁止模式

- 在 config.py 中硬编码 key 默认值（可空 base_url 除外，README 已说明语义）
- 打印密钥明文（即使打码也要谨慎）
- 在 utils 层 import agents / tools / rag 业务模块

## 推荐模式

- 新增基础设施功能（如缓存、重试）先在 utils 层沉淀，再被业务层复用
- 配置变更遵循 .env.example 同步更新
