# 第4章代码截图清单

以下截图建议均基于项目中的真实代码文件整理，便于后续在论文第 4 章“模块实现”小节中替换占位图。建议单张代码截图尽量控制在 15 至 25 行，并保留函数名、关键参数与少量上下文，以增强可读性。

| 序号 | 模块名称 | 推荐截图文件路径 | 推荐截图函数名/类名 | 推荐截图代码起止行号 | 为什么这一段适合截图 |
| --- | --- | --- | --- | --- | --- |
| 1 | MinerU2.5 解析调用 | [src/loaders/mineru_loader.py](/Users/user/毕设/rag-project/src/loaders/mineru_loader.py#L73) | `_run_mineru_and_read_markdown` | 73-112 | 该段直接展示 `mineru` 命令行调用、输出目录定位与 Markdown 回读逻辑，能够真实体现文档解析模块如何接入 MinerU2.5。 |
| 2 | 语义切块与元数据绑定 | [src/chunkers/chunking.py](/Users/user/毕设/rag-project/src/chunkers/chunking.py#L88) | `chunk_markdown_file` | 88-146 | 该段包含标题分块、递归切分、页码锚点提取、`page_labels`/`headers`/`file_id`/`user_id` 注入，是“切块 + 元数据绑定”最核心的实现。 |
| 3 | bge-m3 模型加载与批量编码 | [src/embedder/bge.py](/Users/user/毕设/rag-project/src/embedder/bge.py#L19) | `BGEEmbedding.__init__`、`embed_texts` | 19-91 | 同时覆盖模型路径解析、设备选择、批量编码与向量结果回填，适合说明系统如何完成 `bge-m3` 的工程化封装。 |
| 4 | 向量数据库写入 | [api/api_manager.py](/Users/user/毕设/rag-project/api/api_manager.py#L119) | `process_ingestion_task` | 119-139 | 该段展示切块结果如何整理为 `texts` 与 `metadatas` 并调用 `vector_store.add_texts` 写入 Chroma，是离线知识入库的关键位置。 |
| 5 | 初筛检索 | [api/api_chat.py](/Users/user/毕设/rag-project/api/api_chat.py#L76) | `chat_with_rag` | 76-99 | 该段包含权限过滤、来源过滤与 `vector_store.similarity_search` 调用，能够准确反映系统首阶段候选召回实现。 |
| 6 | 重排序 | [api/api_chat.py](/Users/user/毕设/rag-project/api/api_chat.py#L101) | `chat_with_rag` | 101-113 | 该段直接展示 `bge-reranker-v2-m3` 对查询-候选对进行打分，并按分数重排截取最终 Top-K 的过程，适合作为精排代码截图。 |
| 7 | Prompt 构造 | [api/api_chat.py](/Users/user/毕设/rag-project/api/api_chat.py#L149) | `chat_with_rag` | 149-180 | 该段同时包含系统级 Prompt、上下文编号拼装与最终用户输入构造，能够直接说明“受约束生成”的落地方式。 |
| 8 | 引用标记解析逻辑 | [frontend/src/App.vue](/Users/user/毕设/rag-project/frontend/src/App.vue#L656) | `renderMarkdown` | 656-670 | 该段仅保留回答文本中 `[n]` 标记的正则解析、序号重映射与可点击引用按钮生成逻辑，长度适中，适合单独作为“引用标记解析”截图。 |
| 9 | 引用到元数据的映射逻辑 | [api/api_chat.py](/Users/user/毕设/rag-project/api/api_chat.py#L123) | `chat_with_rag` | 123-147 | 该段集中展示证据结果如何映射为 `index`、`source`、`pages`、`content`、`full_content`、`score` 等字段，能够直接体现回答后处理中的引用元数据绑定逻辑。 |

## 建议对应图片文件名

- `parse_call_code.png`
- `chunk_meta_code.png`
- `embedding_model_code.png`
- `vector_store_code.png`
- `retrieval_initial_code.png`
- `rerank_code.png`
- `prompt_build_code.png`
- `citation_parse_code.png`
- `citation_mapping_code.png`

## 补充说明

- 若论文版面有限，优先保留序号 1、2、5、7、8、9 六张截图；其中序号 8 与序号 9 已将“引用映射 / 回答后处理”拆为两张短截图，避免出现大段代码截图过长的问题。
- 目前项目中向量库运行时主链路以 Chroma 为准，相关代码位于 [api/core.py](/Users/user/毕设/rag-project/api/core.py#L71) 与 [api/api_manager.py](/Users/user/毕设/rag-project/api/api_manager.py#L138)。
- 当前 PDF 入库链路中的页码信息依赖 Markdown 中是否存在页码锚点；若截图需体现 `page_labels` 字段，建议优先截取 [src/chunkers/chunking.py](/Users/user/毕设/rag-project/src/chunkers/chunking.py#L111) 附近代码。 
- 若后续仍希望与现有 `added_sections.tex` 中的图名保持一致，可将序号 8、9 两张图作为 `citation_code.png` 的拆分来源，或在论文图中选择其中一张主图、另一张放入答辩版补充材料。 
