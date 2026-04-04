# 4.3 章节素材整理总结

## 当前结论

- 已具备写入论文 4.3 节所需的核心材料。
- 已筛选出 3 个可直接入表的真实案例：
  - `q018`：语义相关但证据对象不一致
  - `q024`：高召回下噪声增多
  - `q034`：跨块/跨页证据割裂
- 已生成两份可直接写入论文的 LaTeX 表格：
  - `table_dense_limit_cases.tex`
  - `table_retrieval_case_compare.tex`

## 已完成的工作

- 基于 `experiments/end2end/outputs/detailed_results.csv` 提取单阶段与双阶段检索结果。
- 基于 `experiments/end2end/data/test_queries.json` 核对真实查询与标准答案。
- 基于 `experiments/end2end/data/corpus_chunks.json` 回看真实 chunk 文本。
- 对最终案例所涉及的关键证据页码进行了二次回查：
  - 可抽文本 PDF 使用 `pdftotext`；
  - 扫描型 PDF 使用 `pdftoppm + tesseract` OCR。

## 当前仍需说明的材料边界

- 端到端评测产物中的 `page` / `page_labels` 基本退化为 `1`，不能直接作为论文页码依据。
- 因此，本次整理中最终写入论文的页码，采用了对原始 PDF 的二次回查结果，而非直接照抄评测 CSV。
- 非最终入选候选中的个别次级噪声块，没有逐一补齐稳定页码；但这不影响两张最终表格，因为最终表格只使用了已完成页码回查的关键证据。

## 可直接用于论文写作的文件

- `related_files.md`：说明本次整理所依赖的真实项目文件。
- `candidate_cases.md`：给出全部候选案例与筛选理由。
- `best_3_cases.md`：保留最终优选的 3 个案例，结构统一，可直接转写为正文说明。
- `table_dense_limit_cases.tex`：4.3.1 所需表格。
- `table_retrieval_case_compare.tex`：4.3.2 所需表格。

## 结论性判断

- 在“不编造案例、不引入项目之外技术设定”的约束下，当前目录中的材料已经足以支撑论文 4.3 节案例表与对比表的撰写。
- 需要注意的是，文中若补充“页码来源说明”，应表述为“根据原始 PDF 回查补录”，而不应表述为“评测文件直接记录了精确页码”。
