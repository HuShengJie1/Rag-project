# 全文表格清单

本文件列出 [thesis/毕业论文.tex](/Users/user/毕设/rag-project/thesis/毕业论文.tex) 中全文 10 张表格，并标注本次统一处理状态。行号以下列当前修改后的文件为准。

| 序号 | 当前行号 | 表题 | 标签 | 统一状态 | 说明 |
| --- | --- | --- | --- | --- | --- |
| 1 | 356 | 代表性解析模型/工具在 OmniDocBench v1.5 的多维度端到端性能对比 | `tab:parser_comparison` | 已统一 | 已补 `\small`、`arraystretch`、`adjustbox`，注释改为统一宏 |
| 2 | 445 | 同一工程认证文档在不同解析方案下的本地对比结果 | `tab:local_parser_compare` | 已统一 | 已补统一字号与缩放策略 |
| 3 | 518 | 主流开源中文向量模型检索性能对比（用于榜单参考） | `tab:embedding_models` | 已统一 | 已补 `\small`、`arraystretch`、`adjustbox`，注释改为统一宏 |
| 4 | 553 | 不同 Embedding 模型在 EAC 测试集上的检索性能对比 | `tab:embedding_comparison` | 已统一 | 已补统一字号、行距与缩放策略 |
| 5 | 611 | 单阶段稠密检索在工程认证文档场景下的典型局限性示例 | `tab:dense_limit_cases` | 已统一 | 已补统一字号、行距与缩放策略 |
| 6 | 684 | 典型案例下单阶段检索与双阶段检索结果对比 | `tab:retrieval_case_compare` | 已统一 | 已补统一字号、行距与缩放策略 |
| 7 | 850 | 测试数据集分类及验证目标 | `tab:testset_category` | 已统一 | 已补统一字号、行距与缩放策略 |
| 8 | 1009 | 系统测试案例结果汇总 | `tab:case_test_summary` | 已统一 | 已补统一字号、行距与缩放策略 |
| 9 | 1041 | 不同系统配置下的检索性能对比 | `tab:retrieval_result` | 已统一 | 已补统一字号、行距与缩放策略 |
| 10 | 1069 | 不同系统配置下的生成质量与证据链效果对比 | `tab:generation_result` | 已统一 | 已补统一字号、行距与缩放策略 |

## 统一完成情况汇总

- 已统一表格数：10 / 10
- 未统一表格数：0 / 10

## 当前统一后的共性

1. 所有表格均采用 `booktabs`。
2. 所有表格均采用 `\caption` 在前、`\label` 在后。
3. 所有表格均采用 `\small` 与 `\arraystretch=1.2`。
4. 所有表格均采用 `adjustbox` 的 `max width=\textwidth` 控制宽度。
5. 带注释的表格统一使用 `\thesistablenote`。
