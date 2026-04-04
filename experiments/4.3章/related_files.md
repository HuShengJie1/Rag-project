# 4.3 章节素材相关文件清单

## 一、核心实验输出

- `experiments/end2end/outputs/detailed_results.csv`
  - 4.3 节案例整理的核心依据。
  - 记录了 `S1`（单阶段稠密检索）、`S2`（稠密检索 + 重排序）和 `S3` 的逐题结果，包含 `query`、`gold_answer`、`dense_chunks`、`reranked_chunks`、`retrieval_rank` 等字段。

- `experiments/end2end/outputs/retrieval_results.csv`
  - 用于确认各系统检索指标的总体差异。
  - 文件显示 `S1` 的 `MRR=0.8324`，`S2` 的 `MRR=0.8782`，可作为 4.3 节定量背景。

- `experiments/end2end/outputs/summary_results.csv`
  - 记录检索、生成与证据链相关的总体指标。
  - 可辅助说明引入重排序后，证据链相关指标明显改善。

- `experiments/end2end/reports/chapter5_result_summary.md`
  - 明确了 `S1/S2/S3` 的系统配置含义。
  - 可据此确认本文 4.3 节中“单阶段检索”对应 `Dense-RAG`，“双阶段检索”对应 `Dense+Rerank-RAG`。

- `experiments/end2end/reports/chapter5_observations.md`
  - 对总体指标变化给出简要观察结论。
  - 适合作为 4.3 节中“重排序确有增益”的辅助文字依据。

## 二、核心输入数据

- `experiments/end2end/data/test_queries.json`
  - 给出真实测试查询、标准答案与标准证据文档。
  - 本次筛选的 `q018`、`q024`、`q032`、`q034`、`q049` 均来自该文件。

- `experiments/end2end/data/corpus_chunks.json`
  - 给出评测时实际使用的 chunk 文本、`chunk_id`、`file_path` 与基础元数据。
  - 可用于回看检索结果中的具体片段内容。

## 三、实验脚本

- `experiments/end2end/scripts/eval_rag_system.py`
  - 定义了 `S1= Dense-RAG`、`S2= Dense+Rerank-RAG`、`S3= Dense+Rerank+ConstrainedPrompt`。
  - 也是 `dense_chunks` 与 `reranked_chunks` 字段的生成逻辑来源。

- `experiments/end2end/scripts/build_corpus_chunks.py`
  - 说明 `corpus_chunks.json` 的构建方式。
  - 同时解释了 `page` 字段来自 `page_labels`，因此可用于核查页码元数据为何退化。

## 四、用于页码与原文回查的源文件

- `data/parsed/md/附件1-9  信息学院试卷命题及课程目标达成度评价实施细则.md`
  - `q018` 与 `q024` 的正确证据来源。
  - 可直接验证“前两届试题重复率不超过 30\%”与“开卷题中可直接从教材找到答案的题目分值不超过总分值的 20\%”。

- `data/parsed/md/附件1-15  上海海洋大学信息学院专业教学质量持续改进工作指导意见.md`
  - `q034` 的关键证据来源。
  - 其中同时包含“毕业要求至少每二年综合评价一次”和“课程体系每两年局部调整”的真实条文。

- `data/parsed/md/附件1-5  上海海洋大学信息学院课程体系合理性评价办法.md`
  - `q034` 中单阶段检索容易命中的相邻但不充分证据来源。
  - 有助于说明“相近条款优先于真正支撑条款”的问题。

- `data/parsed/md/附件1-11 上海海洋大学本科生学籍管理条例.md`
  - `q032`、`q049` 的候选与对照证据来源。
  - 可反映单阶段检索在学籍管理类条款中的误召回现象。

- `data/parsed/md/附件1-12 上海海洋大学学士学位授予工作细则.md`
  - `q032` 的正确证据来源。
  - 可验证“留校察看及以上处分”与“不授予学士学位”的对应关系。

## 五、原始 PDF（用于页码补录）

- `data/system_docs/附件1-9  信息学院试卷命题及课程目标达成度评价实施细则.pdf`
- `data/system_docs/附件1-15  上海海洋大学信息学院专业教学质量持续改进工作指导意见.pdf`
- `data/system_docs/附件1-5  上海海洋大学信息学院课程体系合理性评价办法.pdf`
- `data/system_docs/附件1-11 上海海洋大学本科生学籍管理条例.pdf`
- `data/system_docs/附件1-12 上海海洋大学学士学位授予工作细则.pdf`
- `data/system_docs/附件1-7 上海海洋大学信息学院课程教学工作基本规范及考核计算办法.pdf`

## 六、核查结论

- 端到端评测文件中的 `page` / `page_labels` 基本退化为 `1`，不能直接作为论文页码依据。
- 因此，本次整理对最终入选案例的关键证据页码进行了二次回查：
  - 可直接抽文本的 PDF 使用 `pdftotext` 回查；
  - 扫描型 PDF 使用 `pdftoppm + tesseract` OCR 回查。
- 最终 LaTeX 表格中的页码，以二次回查结果为准；若某些非入选候选的次要噪声块未完全回查，将在相应说明中明确标注。
