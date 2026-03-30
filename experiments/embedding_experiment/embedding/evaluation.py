from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd


def _parse_ground_truth_doc_ids(value: object) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, (list, tuple, set)):
        return {str(x).strip() for x in value if str(x).strip()}
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return set()
    text = text.replace("，", ",").replace("；", ",")
    parts = []
    for segment in text.split("|"):
        parts.extend(segment.split(","))
    return {part.strip() for part in parts if part.strip()}


def evaluate_retrieval(
    query_df: pd.DataFrame,
    retrieved_indices: np.ndarray,
    retrieved_scores: np.ndarray,
    chunks: list[dict],
    *,
    k_values: Iterable[int] = (1, 5, 10),
) -> tuple[dict, pd.DataFrame]:
    k_values = sorted(set(int(k) for k in k_values if int(k) > 0))
    if not k_values:
        raise ValueError("k_values must contain at least one positive integer.")
    if len(query_df) != retrieved_indices.shape[0]:
        raise ValueError("Mismatch between number of queries and retrieval results.")

    detail_rows = []

    for row_idx, row in query_df.reset_index(drop=True).iterrows():
        gt_doc_ids = _parse_ground_truth_doc_ids(row.get("ground_truth_doc_ids", ""))
        top_indices = retrieved_indices[row_idx].tolist()
        top_scores = retrieved_scores[row_idx].tolist()

        ranked_doc_ids = []
        ranked_chunk_ids = []
        first_hit_rank = 0

        for rank, chunk_index in enumerate(top_indices, start=1):
            if chunk_index < 0 or chunk_index >= len(chunks):
                ranked_doc_ids.append("")
                ranked_chunk_ids.append("")
                continue

            chunk = chunks[chunk_index]
            doc_id = str(chunk.get("original_doc_id", "")).strip()
            chunk_id = str(chunk.get("chunk_id", "")).strip()
            ranked_doc_ids.append(doc_id)
            ranked_chunk_ids.append(chunk_id)

            if first_hit_rank == 0 and doc_id in gt_doc_ids:
                first_hit_rank = rank

        rr = 1.0 / first_hit_rank if first_hit_rank > 0 else 0.0
        detail = {
            "qa_id": row.get("qa_id"),
            "question": row.get("question", ""),
            "ground_truth_doc_ids": "|".join(sorted(gt_doc_ids)),
            "first_hit_rank": first_hit_rank,
            "reciprocal_rank": rr,
        }
        for k in k_values:
            hit = int(first_hit_rank > 0 and first_hit_rank <= k)
            detail[f"hit@{k}"] = hit
            detail[f"recall@{k}"] = hit
        for rank, (doc_id, chunk_id, score) in enumerate(zip(ranked_doc_ids, ranked_chunk_ids, top_scores), start=1):
            detail[f"top{rank}_doc_id"] = doc_id
            detail[f"top{rank}_chunk_id"] = chunk_id
            detail[f"top{rank}_score"] = float(score)

        detail_rows.append(detail)

    detail_df = pd.DataFrame(detail_rows)
    summary = {"num_queries": int(len(detail_df)), "mrr": float(detail_df["reciprocal_rank"].mean())}
    for k in k_values:
        summary[f"hit@{k}"] = float(detail_df[f"hit@{k}"].mean())
        summary[f"recall@{k}"] = float(detail_df[f"recall@{k}"].mean())

    return summary, detail_df
