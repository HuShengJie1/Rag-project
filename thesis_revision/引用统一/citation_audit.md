# 全文引用审计结果

## 章节判定依据

论文主文件 `thesis/毕业论文.tex` 使用 `\section` 作为一级主章节。按正文顺序判定：

1. 第 1 章：绪论
2. 第 2 章：相关理论与核心技术基础
3. 第 3 章：知识助手系统需求分析与总体设计
4. 第 4 章：核心模块设计与对比实验分析
5. 第 5 章：系统实现与整体性能评测
6. 第 6 章：总结与展望

因此，本次“从第三章开始”的处理范围对应 `\section{知识助手系统需求分析与总体设计}` 及其后续章节。

## 引用命令总体统计

- 审计后正文共包含 `66` 个引用命令
- 共涉及 `20` 个参考文献 key

## 各文献 key 首次出现情况

| 首次行号 | 首次章次 | 首次章节 | 首次小节/子节 | 文献 key | 首次上下文命令 | 第三章后是否重复出现 |
| --- | --- | --- | --- | --- | --- | --- |
| 119 | 第1章 | 绪论 | 研究背景 | `gao_retrieval-augmented_2024` | `\cite{gao_retrieval-augmented_2024}` | 是，原第333行重复，已删除 |
| 119 | 第1章 | 绪论 | 研究背景 | `lewis_retrieval-augmented_2021` | `\cite{lewis_retrieval-augmented_2021}` | 否 |
| 124 | 第1章 | 绪论 | 研究意义 | `lzy__2014` | `\cite{lzy__2014, lj__2015}` | 否 |
| 124 | 第1章 | 绪论 | 研究意义 | `lj__2015` | `\cite{lzy__2014, lj__2015}` | 否 |
| 140 | 第1章 | 绪论 | 国内外研究现状/国外研究现状 | `taipalus_vector_2024` | `\cite{taipalus_vector_2024}` | 否 |
| 140 | 第1章 | 绪论 | 国内外研究现状/国外研究现状 | `ma_comprehensive_2025` | `\cite{ma_comprehensive_2025}` | 否 |
| 140 | 第1章 | 绪论 | 国内外研究现状/国外研究现状 | `sys_rag` | `\cite{sys_rag}` | 否 |
| 140 | 第1章 | 绪论 | 国内外研究现状/国外研究现状 | `jegou_product_2011` | `\cite{jegou_product_2011}` | 否 |
| 140 | 第1章 | 绪论 | 国内外研究现状/国外研究现状 | `luo_does_2025` | `\cite{luo_does_2025}` | 否 |
| 145 | 第1章 | 绪论 | 国内外研究现状/国内研究现状 | `zlj_llmrag_2024` | `\cite{zlj_llmrag_2024}` | 否 |
| 145 | 第1章 | 绪论 | 国内外研究现状/国内研究现状 | `ftf_rag_2025` | `\cite{ftf_rag_2025}` | 否 |
| 147 | 第1章 | 绪论 | 国内外研究现状/国内研究现状 | `sry_hsr-ragrag_2025` | `\cite{sry_hsr-ragrag_2025}` | 否 |
| 173 | 第2章 | 相关理论与核心技术基础 | 大规模语言模型与提示工程/大语言模型（LLM）理论基础 | `zhao_merino_2025` | `\cite{zhao_merino_2025}` | 否 |
| 378 | 第4章 | 核心模块设计与对比实验分析 | 复杂结构文档解析与精细化切块策略/解析引擎选型的外部基准参考与本地验证 | `ouyang2024omnidocbenchbenchmarkingdiversepdf` | `\cite{ouyang2024omnidocbenchbenchmarkingdiversepdf}` | 不适用，首次即在第4章 |
| 499 | 第4章 | 核心模块设计与对比实验分析 | 领域知识向量化与 Embedding 模型选型/评测基准与选型约束条件 | `c-mteb` | `\cite{c-mteb}` | 不适用，首次即在第4章 |
| 601 | 第4章 | 核心模块设计与对比实验分析 | 混合检索与重排序（Re-ranking）机制/单阶段稠密检索的局限性分析 | `karpukhin-etal-2020-dense` | `\cite{karpukhin-etal-2020-dense}` | 不适用，首次即在第4章 |
| 601 | 第4章 | 核心模块设计与对比实验分析 | 混合检索与重排序（Re-ranking）机制/单阶段稠密检索的局限性分析 | `reimers-gurevych-2019-sentence` | `\cite{reimers-gurevych-2019-sentence}` | 不适用，首次即在第4章 |
| 603 | 第4章 | 核心模块设计与对比实验分析 | 混合检索与重排序（Re-ranking）机制/单阶段稠密检索的局限性分析 | `iyer-etal-2021-reconsider` | `\cite{iyer-etal-2021-reconsider}` | 不适用，首次即在第4章 |
| 607 | 第4章 | 核心模块设计与对比实验分析 | 混合检索与重排序（Re-ranking）机制/单阶段稠密检索的局限性分析 | `Humeau2020Poly-encoders:` | `\cite{Humeau2020Poly-encoders:,nogueira2020passagererankingbert}` | 不适用，首次即在第4章 |
| 607 | 第4章 | 核心模块设计与对比实验分析 | 混合检索与重排序（Re-ranking）机制/单阶段稠密检索的局限性分析 | `nogueira2020passagererankingbert` | `\cite{Humeau2020Poly-encoders:,nogueira2020passagererankingbert}` | 不适用，首次即在第4章 |

## 第一章与第二章已出现的文献 key

这些 key 按规则视为“旧引用”，从第三章开始原则上不再重复标注：

- `gao_retrieval-augmented_2024`
- `lewis_retrieval-augmented_2021`
- `lj__2015`
- `lzy__2014`
- `jegou_product_2011`
- `luo_does_2025`
- `ma_comprehensive_2025`
- `sys_rag`
- `taipalus_vector_2024`
- `ftf_rag_2025`
- `zlj_llmrag_2024`
- `sry_hsr-ragrag_2025`
- `zhao_merino_2025`

## 第三章及之后的重复情况

审计结果显示，第三章及之后引用了前两章旧文献的情况只有 1 处正文位置：

- 第 333 行，第 3 章“知识助手系统需求分析与总体设计”
- 同一句中两次重复出现 `\cite{gao_retrieval-augmented_2024}`
- 该重复引用已在本次修改中删除

复查结果：修改后，第 3 章及之后已不存在对前两章旧文献的重复引用命令。
