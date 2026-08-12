---
description: src/rag 本地检索管道规则
globs: "**/rag/**"
alwaysApply: false
---
# rag 层规则

> 本规则适用于 `**/rag/**` 匹配的文件（chunking.py / build_index.py / retrieve.py）。
> 生效模式：涉及 RAG 管道时加载

---

## 核心约束

1. **文档变更必须重建索引**：`data/kb_docs/` 内容变化后，必须运行 `.venv\Scripts\python.exe -m src.rag.build_index` 重建，否则检索结果陈旧。why：FAISS 索引是静态快照，不感知文档变化；when：kb_docs 增改后；when_remove：索引改为增量/实时更新时。
2. **索引产物固定落点**：只写 `data/index/kb_index.faiss` + `data/index/kb_metadata.json`，路径不许散落。why：检索/构建/工具三层共享路径契约；when：任何输出；when_remove：存储方案变更时。
3. **chunking 参数一致性**：修改 chunk 大小/重叠等参数时，必须同步考虑检索质量与 eval 证据效果，并在 PROGRESS 登记。why：参数影响 grounding_presence 指标；when：改 chunking.py 时；when_remove：永不（参数是调优面）。
4. **检索封装不进业务逻辑**：retrieve 层只做索引查询返回原始命中（source_title/passage/score），不做路由判断。why：决策 D004 的延伸——证据与决策分离；when：新增检索能力时；when_remove：D004 变更时。

## 代码风格

- embedding 模型配置集中在 build_index.py 顶部常量，禁止散落
- 相对路径基准为仓库根（`data/index/...`），禁止绝对路径（tech-traps 陷阱 2）
- 构建/检索函数签名保持 `(docs_dir / index_dir / query)` 简单参数风格

## 禁止模式

- 在 rag 层 import agents 或 evals 模块
- 对 `kb_metadata.json` 手工编辑（必须走构建脚本）
- 检索结果直接当最终答案输出（那是 main_agent 的职责）

## 推荐模式

- 新文档类别加入 kb_docs 后：重建索引 → 跑 regression 验证 KB 路径
- 检索 top_k 默认 3（与 `logged_search_kb` 一致），调优时记录原因
