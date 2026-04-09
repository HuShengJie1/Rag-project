# TikZ 流程图插入指南

## 插入前准备

请先在论文导言区加入 [tikz_preamble_snippet.tex](/Users/user/毕设/rag-project/thesis_revision/第四章流程图/tikz_preamble_snippet.tex) 中的宏包、TikZ library 与统一样式定义。

推荐做法有两种：

1. 直接把该文件内容复制到 `thesis/毕业论文.tex` 导言区。
2. 在导言区使用 `\input{../thesis_revision/第四章流程图/tikz_preamble_snippet.tex}` 引入。

由于主论文文件位于 `thesis/` 目录下，如果使用 `\input`，相对路径应写成 `../thesis_revision/第四章流程图/...`。

## 各流程图建议插入位置

### 1. 文档解析与语义切块模块实现

- 对应小节位置：[毕业论文.tex](/Users/user/毕设/rag-project/thesis/毕业论文.tex#L513)
- 推荐插入文件：
  - `\input{../thesis_revision/第四章流程图/parse_chunk_impl_flow.tex}`
- 建议放置位置：
  - 放在“文档解析与语义切块模块实现”文字说明之后、代码截图之前。

### 2. 领域知识向量化模块实现

- 对应小节位置：[毕业论文.tex](/Users/user/毕设/rag-project/thesis/毕业论文.tex#L651)
- 推荐插入文件：
  - `\input{../thesis_revision/第四章流程图/embedding_impl_flow.tex}`
- 建议放置位置：
  - 放在“领域知识向量化模块实现”文字说明之后、代码截图之前。

### 3. 双阶段检索与重排序模块实现

- 对应小节位置：[毕业论文.tex](/Users/user/毕设/rag-project/thesis/毕业论文.tex#L830)
- 推荐插入文件：
  - `\input{../thesis_revision/第四章流程图/retrieval_impl_flow.tex}`
- 建议放置位置：
  - 放在“双阶段检索与重排序模块实现”说明段后，用于承接初筛与精排主流程。

### 4. 受约束生成与证据引用联动模块实现

- 对应小节位置：[毕业论文.tex](/Users/user/毕设/rag-project/thesis/毕业论文.tex#L954)
- 推荐插入文件：
  - `\input{../thesis_revision/第四章流程图/generation_impl_flow.tex}`
- 建议放置位置：
  - 放在“受约束生成与证据引用联动模块实现”文字说明之后、Prompt 和引用代码截图之前。

## 推荐插入方式

若你希望后续持续修改图形，优先使用 `\input{...}`：

```tex
\input{../thesis_revision/第四章流程图/parse_chunk_impl_flow.tex}
```

优点：

- 流程图源码与论文正文分离，便于集中维护。
- 后续修改 TikZ 图时不需要反复改正文。

若你希望最终交稿文件更集中，也可以在定稿阶段将对应 `figure` 环境直接复制粘贴到主 `.tex` 文件中。

## 编译建议

- TikZ 图建议使用 XeLaTeX 编译，与当前中文论文环境更一致。
- 若编译中出现浮动体位置不理想，可将 `figure` 的参数从 `[htbp]` 调整为更适合你的版面设置的形式。
