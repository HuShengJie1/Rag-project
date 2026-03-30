from __future__ import annotations

import numpy as np

try:
    import faiss  # type: ignore
except ImportError:  # pragma: no cover
    faiss = None


def _search_numpy(doc_embeddings: np.ndarray, query_embeddings: np.ndarray, top_k: int) -> tuple[np.ndarray, np.ndarray]:
    similarity = query_embeddings @ doc_embeddings.T
    top_k = min(top_k, doc_embeddings.shape[0])
    if top_k <= 0:
        raise ValueError("top_k must be positive.")

    partial = np.argpartition(-similarity, kth=top_k - 1, axis=1)[:, :top_k]
    partial_scores = np.take_along_axis(similarity, partial, axis=1)
    order = np.argsort(-partial_scores, axis=1)
    indices = np.take_along_axis(partial, order, axis=1)
    scores = np.take_along_axis(partial_scores, order, axis=1)
    return indices, scores


def search_top_k(
    doc_embeddings: np.ndarray,
    query_embeddings: np.ndarray,
    *,
    top_k: int = 10,
    use_faiss: bool = True,
) -> tuple[np.ndarray, np.ndarray, str]:
    if doc_embeddings.ndim != 2 or query_embeddings.ndim != 2:
        raise ValueError("Embeddings must be 2D arrays: (num_items, dim).")
    if doc_embeddings.shape[1] != query_embeddings.shape[1]:
        raise ValueError("Embedding dimensions for docs and queries must match.")

    top_k = min(top_k, doc_embeddings.shape[0])
    if top_k <= 0:
        raise ValueError("No document embeddings available for retrieval.")

    docs = doc_embeddings.astype(np.float32, copy=False)
    queries = query_embeddings.astype(np.float32, copy=False)

    if use_faiss and faiss is not None:
        index = faiss.IndexFlatIP(docs.shape[1])
        index.add(docs)
        scores, indices = index.search(queries, top_k)
        return indices, scores, "faiss"

    indices, scores = _search_numpy(docs, queries, top_k)
    return indices, scores, "numpy"
