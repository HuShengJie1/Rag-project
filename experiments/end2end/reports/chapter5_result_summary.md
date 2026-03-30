# 第五章实验结果汇总

## 1. 系统配置

| system | system_name | dense_retrieval | reranker | constrained_prompt |
| --- | --- | --- | --- | --- |
| S1 | Dense-RAG | True | False | False |
| S2 | Dense+Rerank-RAG | True | True | False |
| S3 | Dense+Rerank+ConstrainedPrompt | True | True | True |

## 2. 检索性能

| system | samples | labeled_samples | Hit@5 | Hit@10 | MRR |
| --- | --- | --- | --- | --- | --- |
| S1 | 50 | 49 | 0.8980 | 0.9184 | 0.8324 |
| S2 | 50 | 49 | 0.9184 | 0.9184 | 0.8782 |
| S3 | 50 | 49 | 0.9184 | 0.9184 | 0.8782 |

## 3. 生成质量与证据链

| system | samples | Faithfulness | Answer Relevance | Citation Accuracy | Traceability Success Rate |
| --- | --- | --- | --- | --- | --- |
| S1 | 50 | 0.9606 | 0.8808 | 0.0200 | 0.0400 |
| S2 | 50 | 0.9092 | 0.8925 | 0.6657 | 0.8200 |
| S3 | 50 | 0.9020 | 0.8783 | 0.7657 | 0.9000 |