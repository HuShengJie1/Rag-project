# 4.1 章截图建议

本文件用于指导后续论文插图制作。建议采用“原始 PDF 页面截图 + 不同解析方案对应输出片段”并列展示的方式，以增强本地对比验证的直观性。

## 一、优先截图文档

### 1. `data/system_docs/大数据-2025级本科生培养方案-v13-724.pdf`

- 推荐优先级：高
- 适合表达的问题：
  - 矩阵表格在不同解析方案下的结构保留差异；
  - 课程设置表在不同解析方案下的列结构与阅读顺序差异。

### 2. `data/system_docs/附件1-10 上海海洋大学信息学院课程质量评价办法.pdf`

- 推荐优先级：高
- 适合表达的问题：
  - 扫描型制度文档在弱基线下直接失效；
  - 标题层级、公式与表格混排场景下，MinerU2.5 相比 pipeline 的恢复优势。

## 二、建议截图页面与区域

### 1. 培养方案第 2 页：毕业要求对培养目标的支撑关系矩阵

- 原始页面：
  - `data/system_docs/大数据-2025级本科生培养方案-v13-724.pdf` 第 2 页
- 建议截图区域：
  - 从“毕业要求对培养目标的支撑关系矩阵（有支撑关系打√）”标题开始，到矩阵表格结束为止。
- 配套输出：
  - `experiment/4.1章/generated/pdftotext/bigdata_plan/page_02.txt`
  - `experiment/4.1章/generated/snippets/bigdata_plan/pipeline_page_02.md`
  - `experiment/4.1章/generated/snippets/bigdata_plan/mineru25_page_02.md`
- 建议表达重点：
  - 弱基线仅保留线性文本，无法表达矩阵行列关系；
  - pipeline 虽能恢复表格，但局部“√”符号存在误识别；
  - MinerU2.5 可较稳定保留矩阵结构与支撑关系。

### 2. 培养方案第 4 页：课程设置相关表格

- 原始页面：
  - `data/system_docs/大数据-2025级本科生培养方案-v13-724.pdf` 第 4 页
- 建议截图区域：
  - “（2）公共基础课程”及其下方课程设置表；
  - 若版面允许，可同时包含“公共基础课”表格的表头与前几行。
- 配套输出：
  - `experiment/4.1章/generated/pdftotext/bigdata_plan/page_04.txt`
  - `experiment/4.1章/generated/snippets/bigdata_plan/pipeline_page_04.md`
  - `experiment/4.1章/generated/snippets/bigdata_plan/mineru25_page_04.md`
- 建议表达重点：
  - 纯文本抽取下，列结构被拉平，课程代码、课程名称、学时分配关系不够清晰；
  - MinerU 类方案能恢复表格；其中 MinerU2.5 的文本规范化与结构清晰度更适合直接切块。

### 3. 制度办法第 1 页：标题与一级条款混排

- 原始页面：
  - `data/system_docs/附件1-10 上海海洋大学信息学院课程质量评价办法.pdf` 第 1 页
- 建议截图区域：
  - 页眉、主标题以及“一、评价对象及周期”“二、评价机构”附近区域。
- 配套输出：
  - `experiment/4.1章/generated/pdftotext/course_quality_rules/page_01.txt`
  - `experiment/4.1章/generated/snippets/course_quality_rules/pipeline_page_01.md`
  - `experiment/4.1章/generated/snippets/course_quality_rules/mineru25_page_01.md`
- 建议表达重点：
  - `pdftotext` 输出为空；
  - pipeline 已能恢复正文，但标题层级与版头信息组织不够稳定；
  - MinerU2.5 的标题恢复更接近人工阅读顺序。

### 4. 制度办法第 4 页：表格与公式混排

- 原始页面：
  - `data/system_docs/附件1-10 上海海洋大学信息学院课程质量评价办法.pdf` 第 4 页
- 建议截图区域：
  - “表1 课程目标与课程考核二维矩阵”；
  - 表格下方公式（2）和公式（3）区域。
- 配套输出：
  - `experiment/4.1章/generated/pdftotext/course_quality_rules/page_04.txt`
  - `experiment/4.1章/generated/snippets/course_quality_rules/pipeline_page_04.md`
  - `experiment/4.1章/generated/snippets/course_quality_rules/mineru25_page_04.md`
- 建议表达重点：
  - 弱基线为空输出；
  - pipeline 的公式恢复明显失真；
  - MinerU2.5 同时保留了表格结构与公式语义，更能支撑后续结构化切块。

## 三、建议的论文展示方式

1. 若正文版面有限，优先保留两组截图：
   - 培养方案第 2 页矩阵表格；
   - 制度办法第 4 页公式与表格混排。
2. 若可以增加一幅补充图，可加入制度办法第 1 页标题层级对比，用于强调扫描件场景下弱基线失效的问题。
3. 每组图建议保持统一结构：
   - 左侧为原始 PDF 局部截图；
   - 右侧依次展示弱基线、pipeline、MinerU2.5 的输出片段。

## 四、截图后建议配套说明句式

- 可用于表格结构案例：
  - “由图可见，在同一矩阵表格页面中，纯文本抽取难以保留稳定的行列对应关系，传统 pipeline 虽可恢复表格外形，但在关键符号识别上仍存在噪声；相比之下，MinerU2.5 能够较完整地保留矩阵结构及其语义关系。”
- 可用于扫描件案例：
  - “对于扫描型制度文档，弱基线方法无法获得有效文本结果，而 MinerU2.5 在标题层级、表格结构与公式可读性方面均表现出更好的稳定性，因此更适合作为后续语义感知切块的上游解析方案。”
