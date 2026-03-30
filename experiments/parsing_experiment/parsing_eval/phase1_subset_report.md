# Phase 1 Parsing Subset Report

- Candidate pool size: 25
- Recommended subset size: 15 (target=15)
- Table-rich docs: 10
- Scanned docs: 4
- Complex-layout docs: 11
- Need manual review: 3

## Category Distribution
- attainment_report: 1
- handbook: 1
- policy: 8
- quality_report: 1
- self_evaluation_report: 1
- syllabus: 1
- training_program: 2

## Recommended Strategy
- Cover each inferred document type at least once before filling feature-heavy slots.
- Prefer documents with strong table, OCR, or complex-layout signals because they are more discriminative for parser comparison.
- Keep `need_manual_review` samples in the subset when they add diversity, but mark them explicitly for later manual adjustment.

## Recommended Documents
- 7 | 河南大学（软件学院） 软件学院课程目标达成度评价实施办法 | type=attainment_report | table=yes | scanned=no | complex=yes | manual_review=false | reason=doc_type=attainment_report; table_rich; structure_complex
- 6 | 复旦大学 复旦大学大数据学院本科生课程学习手册 | type=handbook | table=yes | scanned=no | complex=yes | manual_review=false | reason=doc_type=handbook; table_rich; structure_complex
- 16 | 华南师范大学（计算机学院） 本科专业课程评价实施细则（修订版） | type=policy | table=yes | scanned=yes | complex=yes | manual_review=false | reason=doc_type=policy; table_rich; scanned; structure_complex
- 31 | 清华大学 清华大学2023-2024学年本科教学质量报告 | type=quality_report | table=need_manual_review | scanned=no | complex=yes | manual_review=true | reason=doc_type=quality_report; structure_complex; need_manual_review
- 39 | 昆明理工大学 自评报告（机器人工程专业新增列学士学位授权） | type=self_evaluation_report | table=yes | scanned=no | complex=yes | manual_review=false | reason=doc_type=self_evaluation_report; table_rich; structure_complex
- 5 | 北方工业大学 《大数据概论》课程教学大纲 | type=syllabus | table=yes | scanned=no | complex=yes | manual_review=false | reason=doc_type=syllabus; table_rich; structure_complex
- 2 | 北京理工大学 数据科学与大数据技术专业培养方案 | type=training_program | table=yes | scanned=no | complex=yes | manual_review=false | reason=doc_type=training_program; table_rich; structure_complex
- 21 | 华南师范大学（计算机学院） 教学督导工作实施细则 | type=policy | table=yes | scanned=yes | complex=yes | manual_review=false | reason=doc_type=policy; table_rich; scanned; structure_complex
- 15 | 华南师范大学（计算机学院） 本科专业培养目标评价实施细则（修订版） | type=policy | table=no | scanned=yes | complex=need_manual_review | manual_review=true | reason=doc_type=policy; scanned; need_manual_review
- 17 | 华南师范大学（计算机学院） 本科专业毕业要求评价实施细则（修订版） | type=policy | table=no | scanned=yes | complex=need_manual_review | manual_review=true | reason=doc_type=policy; scanned; need_manual_review
- 27 | 华北电力大学（控制与计算机工程学院） 教学督导工作细则 | type=policy | table=no | scanned=no | complex=no | manual_review=false | reason=doc_type=policy
- 19 | 合肥工业大学（计算机与信息学院_软件学院） 计算机与信息学院毕业设计制度 | type=policy | table=no | scanned=no | complex=no | manual_review=false | reason=doc_type=policy
- 1 | 河北工业大学 数据科学与大数据技术专业2023级本科人才培养方案 | type=training_program | table=yes | scanned=no | complex=yes | manual_review=false | reason=doc_type=training_program; table_rich; structure_complex
- 14 | 山东科技大学（计算机学院） 内部跟踪评价实施细则 | type=policy | table=yes | scanned=no | complex=yes | manual_review=false | reason=doc_type=policy; table_rich; structure_complex
- 24 | 合肥工业大学（计算机与信息学院_软件学院） 计算机与信息学院实习基地制度 | type=policy | table=yes | scanned=no | complex=yes | manual_review=false | reason=doc_type=policy; table_rich; structure_complex
