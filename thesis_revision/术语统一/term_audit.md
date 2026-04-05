# 全文术语审计结果

## 审计范围说明

本次审计对象为论文主文件 `thesis/毕业论文.tex` 中真实出现、且具有英文简称或固定缩写形态的专有名词，重点覆盖以下类型：

- 技术框架与方法术语
- 检索、解析与生成相关术语
- 评价指标与数据集简称
- 系统组件与运行环境术语

术语首次出现位置以论文整体阅读顺序为准，优先按摘要、正文、图表标题的顺序判定。

## 审计结果表

| 术语 | 中文名称 | 英文全称 | 首次出现位置 | 当前状态 | 处理说明 |
| --- | --- | --- | --- | --- | --- |
| EAC | 工程教育专业认证 | Engineering Education Accreditation | 第 92 行 | 已统一 | 摘要首次完整定义，后文重复的“工程教育专业认证（EAC）”改为 `EAC` 或自然简称化表达。 |
| OBE | 成果导向教育 | Outcome-Based Education | 第 92 行 | 已统一 | 摘要首次完整定义，后文冗余写法统一压缩为 `OBE`。 |
| RAG | 检索增强生成 | Retrieval-Augmented Generation | 第 92 行 | 已统一 | 摘要首次完整定义；正文、小节标题与结论中重复“全称+简称”已改为 `RAG` 或 `RAG 框架`。 |
| MRR | 检索排序质量 | Mean Reciprocal Rank | 第 96 行 | 原本合规 | 首次出现已为“全称+简称”，后文保留 `MRR` 或指标名称，不作额外改写。 |
| LLM | 大规模语言模型 | Large Language Model | 第 117 行 | 已统一 | 修正了正文中 `Large Language Models` 与 `大语言模型(LLM)` 的混用；后文统一为 `LLM`。 |
| VDB | 向量数据库 | Vector Database | 第 140 行 | 已统一 | 首次出现完整定义；后文“向量数据库（VDB）”改为 `VDB` 或中文全称。 |
| PQ | 乘积量化 | Product Quantization | 第 140 行 | 已统一 | 首次出现完整定义；后文重复“全称+简称”改为 `PQ`。 |
| API | 应用程序编程接口 | Application Programming Interface | 第 155 行 | 原本基本合规 | 首次出现已完整定义，后文主要以具体产品接口名出现，未做额外替换。 |
| NLU | 自然语言理解 | Natural Language Understanding | 第 172 行 | 原本合规 | 首次出现完整定义，后文未发现需统一的重复写法。 |
| NLG | 自然语言生成 | Natural Language Generation | 第 172 行 | 原本合规 | 首次出现完整定义，后文未发现需统一的重复写法。 |
| MIPS | 最大内积搜索 | Maximum Inner Product Search | 第 212 行 | 原本合规 | 首次出现完整定义，后文无明显冲突。 |
| KNN | K近邻 | K-Nearest Neighbor | 第 245 行 | 原本合规 | 首次出现完整定义，后文无重复定义。 |
| ANN | 近似最近邻搜索 | Approximate Nearest Neighbor | 第 247 行 | 已统一 | 原文先出现 `ANN` 后补全称，现已改为先用中文全称描述，正文首次定义放在第 247 行。 |
| HNSW | 分层可导航小世界图 | Hierarchical Navigable Small World | 第 248 行 | 原本合规 | 首次出现完整定义。 |
| PDF | 可移植文档格式 | Portable Document Format | 第 286 行 | 已统一 | 原文先直接使用 `PDF`，现已在首次出现处补齐全称。 |
| VLM | 视觉语言模型 | Vision Language Model | 第 354 行 | 原本合规 | 首次出现完整定义，后文简称使用正常。 |
| OCR | 光学字符识别 | Optical Character Recognition | 第 381 行 | 已统一 | 原文首次出现为 `OCR`，现已补齐英文全称与简称。 |
| C-MTEB | 中文海量文本嵌入评测基准 | Chinese Massive Text Embedding Benchmark | 第 499 行 | 原本合规 | 首次出现完整定义。 |
| nDCG@10 | 归一化折损累计增益 | Normalized Discounted Cumulative Gain | 第 499 行 | 原本合规 | 首次出现完整定义。 |
| Hit@K | 命中率指标 | Hit at K | 第 549 行 | 原本合规 | 首次出现完整定义。 |
| DPR | 稠密段落检索 | Dense Passage Retrieval | 第 601 行 | 原本合规 | 首次出现完整定义。 |
| GPU | 图形处理器 | Graphics Processing Unit | 第 824 行 | 原本合规 | 首次出现完整定义。 |
| QA | 问答对 | Question-Answer Pairs | 第 844 行 | 原本合规 | 首次出现完整定义。 |

## 需说明的歧义项

以下项目在全文中出现，但本次未按“全称+简称”模板机械改写：

- `HSR-RAG`：属于文献中已有方法名，保留原命名方式。
- `Naive RAG`、`Advanced RAG`、`Dense-RAG`：属于方法类别或系统配置名，保留为既有写法。
- `Seq2Seq`、`Top-K`、`Top-N`、`TEDS-S`：更接近模型结构、记号或指标记法，不按普通中文术语简称链条处理。
- `Vue`、`LangChain`、`DeepSeek API`、`Kimi API`：属于产品名或框架名，不适合改写为中文全称主导的简称链。
