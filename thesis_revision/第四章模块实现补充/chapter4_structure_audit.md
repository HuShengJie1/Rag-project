# 第4章结构审查记录

审查对象：`thesis/毕业论文.tex`

审查结论：当前第 4 章标题已为“核心模块设计与实现”，4.1、4.2、4.3、4.4 四个模块均已存在，且各模块内部采用 `\subsubsection` 作为下一层级标题。按照“不改原文、只追加”的约束，新增“模块实现”内容应以新的 `\subsubsection` 形式分别插入到各模块现有内容末尾、下一 `\subsection` 之前。

| 模块编号 | 现有模块标题 | 现有最后一个子小节标题 | 现有模块末尾定位 | 建议追加位置 |
| --- | --- | --- | --- | --- |
| 4.1 | 复杂结构文档解析与精细化切块策略 | 语义感知与精细化切块策略 | [thesis/毕业论文.tex](/Users/user/毕设/rag-project/thesis/毕业论文.tex#L511) 之后、[thesis/毕业论文.tex](/Users/user/毕设/rag-project/thesis/毕业论文.tex#L514) 之前 | 在 4.1 末尾追加 `\subsubsection{文档解析与语义切块模块实现}` |
| 4.2 | 领域知识向量化与 Embedding 模型选型 | 本地测试集验证与最终选型 | [thesis/毕业论文.tex](/Users/user/毕设/rag-project/thesis/毕业论文.tex#L608) 之后、[thesis/毕业论文.tex](/Users/user/毕设/rag-project/thesis/毕业论文.tex#L611) 之前 | 在 4.2 末尾追加 `\subsubsection{领域知识向量化模块实现}` |
| 4.3 | 混合检索与重排序（Re-ranking）机制 | 双阶段检索框架设计 | [thesis/毕业论文.tex](/Users/user/毕设/rag-project/thesis/毕业论文.tex#L747) 之后、[thesis/毕业论文.tex](/Users/user/毕设/rag-project/thesis/毕业论文.tex#L748) 之前 | 在 4.3 末尾追加 `\subsubsection{双阶段检索与重排序模块实现}` |
| 4.4 | 提示工程设计与生成约束 | 与系统证据链机制的协同作用 | [thesis/毕业论文.tex](/Users/user/毕设/rag-project/thesis/毕业论文.tex#L829) 之后、[thesis/毕业论文.tex](/Users/user/毕设/rag-project/thesis/毕业论文.tex#L831) 之前 | 在 4.4 末尾追加 `\subsubsection{受约束生成与证据引用联动模块实现}` |

## 现有第4章层级摘要

- 第 4 章起始位置：[thesis/毕业论文.tex](/Users/user/毕设/rag-project/thesis/毕业论文.tex#L366)
- 4.1 起始位置：[thesis/毕业论文.tex](/Users/user/毕设/rag-project/thesis/毕业论文.tex#L368)
- 4.2 起始位置：[thesis/毕业论文.tex](/Users/user/毕设/rag-project/thesis/毕业论文.tex#L514)
- 4.3 起始位置：[thesis/毕业论文.tex](/Users/user/毕设/rag-project/thesis/毕业论文.tex#L611)
- 4.4 起始位置：[thesis/毕业论文.tex](/Users/user/毕设/rag-project/thesis/毕业论文.tex#L748)

## 审查说明

- 当前第 4 章不存在“模块实现”类独立小节，适合按老师要求在每个模块末尾补入实现说明、流程图占位与代码截图占位。
- 第 5 章起始于 [thesis/毕业论文.tex](/Users/user/毕设/rag-project/thesis/毕业论文.tex#L831)，因此 4.4 的新增内容必须插入在该位置之前。
