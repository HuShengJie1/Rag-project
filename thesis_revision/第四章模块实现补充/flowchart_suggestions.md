# 第4章流程图建议

## 1. 文档解析与语义切块模块实现流程图

- 图标题：文档解析与语义切块模块实现流程图
- 节点顺序：上传文件 -> 文件类型判断 -> 调用 MinerU2.5 解析 -> 生成并持久化 Markdown -> 按标题层级切块 -> 超长块递归切分 -> 绑定元数据 -> 输出文本块
- 节点文字：
  - 用户上传 PDF/DOCX/MD/TXT
  - 后端识别文件后缀
  - PDF/DOCX 调用 MinerU2.5 生成 Markdown
  - 保存完整 Markdown 供后续证据回溯
  - 基于 Markdown 标题进行一级语义切块
  - 对超长块执行递归字符切分
  - 注入 `file_id`、`user_id`、`headers`、`page_labels`
  - 形成可入库的 chunk 列表
- 是否需要强调 metadata、page、source_path 等信息：需要。建议在“绑定元数据”节点旁标注 `headers / page_labels / full_md_path / source`，突出后续溯源基础。

## 2. 领域知识向量化模块实现流程图

- 图标题：领域知识向量化与向量存储模块实现流程图
- 节点顺序：读取 chunk -> 加载 bge-m3 -> 批量编码 -> 构造向量库元数据 -> 写入 Chroma -> 完成索引构建
- 节点文字：
  - 读取语义切块结果
  - 初始化 bge-m3 嵌入模型
  - 按批次执行文本向量编码
  - 组装 `chunk_id`、`source`、`page_labels`、`headers`
  - 调用 Chroma `add_texts`
  - 形成可检索向量索引
- 是否需要强调 metadata、page、source_path 等信息：需要。建议强调 `chunk_id`、`page_labels` 与 `source`，因为这些字段会继续传递到检索与引用模块。

## 3. 双阶段检索与重排序模块实现流程图

- 图标题：双阶段检索与重排序模块实现流程图
- 节点顺序：输入问题 -> 来源与权限过滤 -> 初筛检索 -> 构造查询-候选对 -> bge-reranker-v2-m3 重排序 -> 选取 Top-K 证据 -> 传递证据包
- 节点文字：
  - 用户输入自然语言问题
  - 根据 `user_id` 与 `file_id` 过滤候选范围
  - Chroma 相似度检索返回 Top-30
  - 构造 Query-Chunk 配对
  - 计算重排序分数
  - 按分数降序筛选最终证据
  - 输出带编号的 evidence list
- 是否需要强调 metadata、page、source_path 等信息：需要。建议在“传递证据包”节点标注 `index / source / pages / full_content / score`。

## 4. 受约束生成与证据引用联动模块实现流程图

- 图标题：受约束生成与证据引用联动模块实现流程图
- 节点顺序：构造系统 Prompt -> 拼接编号上下文 -> 调用 Kimi API -> 返回带引用回答 -> 前端解析引用编号 -> 映射证据详情并高亮展示
- 节点文字：
  - 写入系统级约束 Prompt
  - 将证据编号、来源与页码拼接进上下文
  - 调用 Kimi 生成流式回答
  - 返回形如 `[1][2]` 的引用标记
  - 前端解析引用编号
  - 根据 `evidence_list` 打开原文详情
  - 在完整 Markdown 中执行高亮定位
- 是否需要强调 metadata、page、source_path 等信息：需要。建议突出 `index`、`pages`、`source` 与 `full_content`，这是实现前后端联动的关键字段。
