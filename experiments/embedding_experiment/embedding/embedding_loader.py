from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, Mapping

import numpy as np
from sentence_transformers import SentenceTransformer


ALLOWED_MODELS = [
    "BAAI/bge-large-zh-v1.5",
    "BAAI/bge-m3",
    "openbmb/MiniCPM-Embedding",
]

_QUERY_PREFIX = {
    "BAAI/bge-large-zh-v1.5": "为这个句子生成表示以用于检索相关文章：",
    "BAAI/bge-m3": "为这个句子生成表示以用于检索相关文章：",
}

PROJECT_ROOT = Path(__file__).resolve().parents[3]
LOCAL_MODEL_ROOT = Path(os.getenv("LOCAL_MODEL_ROOT", PROJECT_ROOT / "models/hf_cache/hub"))
LOCAL_MODEL_PATHS = {
    "BAAI/bge-large-zh-v1.5": LOCAL_MODEL_ROOT / "BAAI/bge-large-zh-v1___5",
    "BAAI/bge-m3": LOCAL_MODEL_ROOT / "BAAI/bge-m3",
    "openbmb/MiniCPM-Embedding": LOCAL_MODEL_ROOT / "openbmb/MiniCPM-Embedding",
}


def load_embedding_model(model_name: str, device: str | None = None) -> SentenceTransformer:
    if model_name not in ALLOWED_MODELS:
        raise ValueError(f"Model {model_name!r} is not in the allowed candidate list.")

    local_path = LOCAL_MODEL_PATHS[model_name]
    if not local_path.exists():
        raise FileNotFoundError(
            f"Local model path does not exist for {model_name}: {local_path}. "
            "Please download models into models/hf_cache/hub first."
        )

    kwargs = {
        "model_name_or_path": str(local_path),
        "device": device,
        "local_files_only": True,
    }
    if model_name == "openbmb/MiniCPM-Embedding":
        kwargs["trust_remote_code"] = True
    return SentenceTransformer(**kwargs)


def format_query_for_model(model_name: str, query: str) -> str:
    prefix = _QUERY_PREFIX.get(model_name, "")
    query = query.strip()
    return f"{prefix}{query}" if prefix else query


def build_doc_embed_text(chunk: Mapping[str, object]) -> str:
    hierarchy_raw = chunk.get("header_hierarchy", [])
    if isinstance(hierarchy_raw, list):
        hierarchy = [str(x).strip() for x in hierarchy_raw if str(x).strip()]
    elif isinstance(hierarchy_raw, str):
        hierarchy = [x.strip() for x in hierarchy_raw.split(">") if x.strip()]
    else:
        hierarchy = []

    section_title = str(chunk.get("section_title", "")).strip()
    text = str(chunk.get("text", "")).strip()

    parts: list[str] = []
    if hierarchy:
        parts.append(f"标题路径: {' > '.join(hierarchy)}")
    if section_title and (not hierarchy or section_title != hierarchy[-1]):
        parts.append(f"小节标题: {section_title}")
    if text:
        parts.append(f"正文: {text}")

    return "\n".join(parts) if parts else text


def _encode_texts(
    model: SentenceTransformer,
    texts: Iterable[str],
    *,
    batch_size: int = 16,
    show_progress_bar: bool = True,
) -> np.ndarray:
    embeddings = model.encode(
        list(texts),
        batch_size=batch_size,
        show_progress_bar=show_progress_bar,
        normalize_embeddings=True,
        convert_to_numpy=True,
    )
    return embeddings.astype(np.float32, copy=False)


def embed_chunks(
    model: SentenceTransformer,
    chunks: list[Mapping[str, object]],
    *,
    batch_size: int = 16,
    show_progress_bar: bool = True,
) -> np.ndarray:
    texts = [build_doc_embed_text(chunk) for chunk in chunks]
    return _encode_texts(model, texts, batch_size=batch_size, show_progress_bar=show_progress_bar)


def embed_queries(
    model: SentenceTransformer,
    model_name: str,
    queries: Iterable[str],
    *,
    batch_size: int = 16,
    show_progress_bar: bool = False,
) -> np.ndarray:
    formatted = [format_query_for_model(model_name, query) for query in queries]
    return _encode_texts(model, formatted, batch_size=batch_size, show_progress_bar=show_progress_bar)
