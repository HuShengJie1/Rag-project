# 4.1 章本地对比验证结果索引

本文件汇总本次本地对比验证中已经实际整理出的输出路径。所有新增整理结果均位于 `experiment/4.1章/generated/`，原始 MinerU 解析产物仍保留在项目既有实验目录中，不做改动。

## 一、文档 A：`data/system_docs/大数据-2025级本科生培养方案-v13-724.pdf`

### 1. 原始文档

- `data/system_docs/大数据-2025级本科生培养方案-v13-724.pdf`

### 2. 纯文本抽取弱基线

- 全文输出：
  - `experiment/4.1章/generated/pdftotext/bigdata_plan/full.txt`
- 按页输出：
  - `experiment/4.1章/generated/pdftotext/bigdata_plan/page_02.txt`
  - `experiment/4.1章/generated/pdftotext/bigdata_plan/page_04.txt`

### 3. 传统 pipeline 类解析结果

- 原始 Markdown：
  - `experiments/embedding_experiment/parsing/outputs/pipeline/大数据-2025级本科生培养方案-v13-724__0e3d9ebe07/大数据-2025级本科生培养方案-v13-724/auto/大数据-2025级本科生培养方案-v13-724.md`
- 原始结构化列表：
  - `experiments/embedding_experiment/parsing/outputs/pipeline/大数据-2025级本科生培养方案-v13-724__0e3d9ebe07/大数据-2025级本科生培养方案-v13-724/auto/大数据-2025级本科生培养方案-v13-724_content_list.json`
- 本次整理的重点页摘录：
  - `experiment/4.1章/generated/snippets/bigdata_plan/pipeline_page_02.md`
  - `experiment/4.1章/generated/snippets/bigdata_plan/pipeline_page_04.md`

### 4. MinerU2.5 解析结果

- 原始 Markdown：
  - `experiments/embedding_experiment/parsing/outputs/vlm/大数据-2025级本科生培养方案-v13-724__0e3d9ebe07/大数据-2025级本科生培养方案-v13-724/hybrid_auto/大数据-2025级本科生培养方案-v13-724.md`
- 原始结构化列表：
  - `experiments/embedding_experiment/parsing/outputs/vlm/大数据-2025级本科生培养方案-v13-724__0e3d9ebe07/大数据-2025级本科生培养方案-v13-724/hybrid_auto/大数据-2025级本科生培养方案-v13-724_content_list.json`
- 本次整理的重点页摘录：
  - `experiment/4.1章/generated/snippets/bigdata_plan/mineru25_page_02.md`
  - `experiment/4.1章/generated/snippets/bigdata_plan/mineru25_page_04.md`

### 5. 最值得截图的页面

- 第 2 页：
  - 展示“毕业要求对培养目标的支撑关系矩阵”。
  - 重点表达：`pdftotext` 仅保留线性文本，pipeline 虽恢复表格但存在勾选符号误识别，MinerU2.5 可较完整保留矩阵结构与符号。
- 第 4 页：
  - 展示课程设置相关表格。
  - 重点表达：复杂表格场景下，纯文本抽取难以维持列结构；pipeline 与 MinerU2.5 均能恢复表格，但 MinerU2.5 的文本归一化与结构清晰度更适合后续切块。

## 二、文档 B：`data/system_docs/附件1-10 上海海洋大学信息学院课程质量评价办法.pdf`

### 1. 原始文档

- `data/system_docs/附件1-10 上海海洋大学信息学院课程质量评价办法.pdf`

### 2. 纯文本抽取弱基线

- 全文输出：
  - `experiment/4.1章/generated/pdftotext/course_quality_rules/full.txt`
- 按页输出：
  - `experiment/4.1章/generated/pdftotext/course_quality_rules/page_01.txt`
  - `experiment/4.1章/generated/pdftotext/course_quality_rules/page_04.txt`
- 说明：
  - 第 1 页与第 4 页文本文件均为空，表明在扫描型制度文档上，简单文本抽取无法提供可用解析结果。

### 3. 传统 pipeline 类解析结果

- 原始 Markdown：
  - `experiments/embedding_experiment/parsing/outputs/pipeline/附件1-10_上海海洋大学信息学院课程质量评价办法__2f8b91b22d/附件1-10 上海海洋大学信息学院课程质量评价办法/auto/附件1-10 上海海洋大学信息学院课程质量评价办法.md`
- 原始结构化列表：
  - `experiments/embedding_experiment/parsing/outputs/pipeline/附件1-10_上海海洋大学信息学院课程质量评价办法__2f8b91b22d/附件1-10 上海海洋大学信息学院课程质量评价办法/auto/附件1-10 上海海洋大学信息学院课程质量评价办法_content_list.json`
- 本次整理的重点页摘录：
  - `experiment/4.1章/generated/snippets/course_quality_rules/pipeline_page_01.md`
  - `experiment/4.1章/generated/snippets/course_quality_rules/pipeline_page_04.md`

### 4. MinerU2.5 解析结果

- 原始 Markdown：
  - `experiments/embedding_experiment/parsing/outputs/vlm/附件1-10_上海海洋大学信息学院课程质量评价办法__2f8b91b22d/附件1-10 上海海洋大学信息学院课程质量评价办法/hybrid_auto/附件1-10 上海海洋大学信息学院课程质量评价办法.md`
- 原始结构化列表：
  - `experiments/embedding_experiment/parsing/outputs/vlm/附件1-10_上海海洋大学信息学院课程质量评价办法__2f8b91b22d/附件1-10 上海海洋大学信息学院课程质量评价办法/hybrid_auto/附件1-10 上海海洋大学信息学院课程质量评价办法_content_list.json`
- 本次整理的重点页摘录：
  - `experiment/4.1章/generated/snippets/course_quality_rules/mineru25_page_01.md`
  - `experiment/4.1章/generated/snippets/course_quality_rules/mineru25_page_04.md`

### 5. 最值得截图的页面

- 第 1 页：
  - 展示标题、一级条款与正文区域。
  - 重点表达：扫描件下 `pdftotext` 为空输出，pipeline 能提取正文但标题层级不够稳定，MinerU2.5 对标题和条款结构恢复更清晰。
- 第 4 页：
  - 展示“表1 课程目标与课程考核二维矩阵”及其下方公式区域。
  - 重点表达：pipeline 对表格恢复尚可，但公式内容严重失真；MinerU2.5 能同时保留表格结构和公式语义，因而更适合后续结构化切块。

## 三、本次生成目录

- 汇总索引：
  - `experiment/4.1章/generated/index.json`
- 生成方式：
  - `experiment/4.1章/run_compare.sh`
  - `experiment/4.1章/run_compare.py`

## 四、可直接用于论文 4.1 的关键对比点

1. 同一矩阵表格页面中，弱基线无法保留行列关系，pipeline 存在局部识别错误，而 MinerU2.5 可稳定输出可复用的表格结构。
2. 同一扫描型制度页面中，弱基线为空输出，pipeline 对正文恢复较好但对公式与层级存在缺陷，MinerU2.5 在结构完整性方面更具优势。
3. 上述差异将直接影响 4.1.2 的精细化切块：当标题、表格和公式边界无法保留时，后续按语义单元进行切块和元数据绑定的可靠性将明显下降。
