#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
import requests
import yaml
from sentence_transformers import CrossEncoder, SentenceTransformer

SYSTEM_META = {
    "S1": {
        "name": "Dense-RAG",
        "dense": True,
        "rerank": False,
        "constrained_prompt": False,
    },
    "S2": {
        "name": "Dense+Rerank-RAG",
        "dense": True,
        "rerank": True,
        "constrained_prompt": False,
    },
    "S3": {
        "name": "Dense+Rerank+ConstrainedPrompt",
        "dense": True,
        "rerank": True,
        "constrained_prompt": True,
    },
}

TOKEN_RE = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]")
CITATION_RE = re.compile(r"\[(?:C|c)?(\d+)\]")
ATTACHMENT_KEY_RE = re.compile(r"附件\s*1\s*-\s*(\d+)")
PROGRAM_KEY_RE = re.compile(r"(大数据-\d{4}级本科生培养方案(?:-v\d+-\d+)?)")
STOP_TOKENS = {
    "的",
    "了",
    "和",
    "与",
    "及",
    "在",
    "是",
    "为",
    "对",
    "中",
    "、",
    "，",
    "。",
    "：",
    "；",
    "（",
    "）",
}


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def load_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_text(path: Path, text: str) -> None:
    ensure_parent(path)
    path.write_text(text, encoding="utf-8")


def to_float(value: Any, ndigits: int = 6) -> float | None:
    if value is None:
        return None
    try:
        return round(float(value), ndigits)
    except Exception:
        return None


def setup_logging(log_file: Path, level: str = "INFO") -> None:
    ensure_parent(log_file)
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.handlers = []

    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)


def load_test_queries(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict):
        if "data" in data and isinstance(data["data"], list):
            samples = data["data"]
        elif "samples" in data and isinstance(data["samples"], list):
            samples = data["samples"]
        else:
            raise ValueError(f"不支持的测试集结构: {path}")
    elif isinstance(data, list):
        samples = data
    else:
        raise ValueError(f"测试集格式错误: {path}")

    normalized: List[Dict[str, Any]] = []
    for i, s in enumerate(samples, start=1):
        if not isinstance(s, dict):
            continue
        query = str(s.get("query", "")).strip()
        if not query:
            continue
        normalized.append(
            {
                "id": str(s.get("id", f"q{i:03d}")),
                "query": query,
                "gold_answer": s.get("gold_answer", ""),
                "gold_evidence_doc": s.get("gold_evidence_doc"),
                "gold_evidence_page": s.get("gold_evidence_page"),
                "gold_chunk_id": s.get("gold_chunk_id"),
                "question_type": s.get("question_type", ""),
            }
        )
    return normalized


def _extract_page(meta: Dict[str, Any], raw: Dict[str, Any]) -> Any:
    page = raw.get("page")
    if page is None:
        page = meta.get("page")
    if page is None:
        labels = meta.get("page_labels")
        if isinstance(labels, list) and labels:
            page = labels[0]
    return page


def load_corpus_chunks(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict):
        if "chunks" in data and isinstance(data["chunks"], list):
            chunks = data["chunks"]
        elif "data" in data and isinstance(data["data"], list):
            chunks = data["data"]
        else:
            raise ValueError(f"不支持的语料结构: {path}")
    elif isinstance(data, list):
        chunks = data
    else:
        raise ValueError(f"语料格式错误: {path}")

    normalized: List[Dict[str, Any]] = []
    for i, c in enumerate(chunks, start=1):
        if not isinstance(c, dict):
            continue
        meta = c.get("metadata") or {}
        text = str(c.get("text") or c.get("chunk_text") or c.get("content") or "").strip()
        if not text:
            continue

        file_path = (
            c.get("file_path")
            or meta.get("file_path")
            or meta.get("source")
            or meta.get("doc_name")
            or ""
        )
        page = _extract_page(meta, c)
        chunk_id = str(c.get("chunk_id") or c.get("id") or f"chunk_{i:05d}")

        normalized.append(
            {
                "chunk_id": chunk_id,
                "text": text,
                "embedding_text": str(c.get("embedding_text") or "").strip(),
                "file_path": str(file_path),
                "page": page,
                "metadata": meta if isinstance(meta, dict) else {},
            }
        )

    if not normalized:
        raise ValueError("语料为空，无法进行检索评测")
    return normalized


def tokenize_text(text: str) -> List[str]:
    tokens = TOKEN_RE.findall(text or "")
    return [t for t in tokens if t not in STOP_TOKENS]


def build_embedding_text(chunk: Dict[str, Any]) -> str:
    explicit = str(chunk.get("embedding_text") or "").strip()
    if explicit:
        return explicit

    meta = chunk.get("metadata", {}) or {}
    headers = meta.get("header_hierarchy") or meta.get("headers") or []
    if not isinstance(headers, list):
        headers = [str(headers)]
    header_values = [str(h).strip() for h in headers if str(h).strip()]

    doc_name = str(
        meta.get("doc_name")
        or Path(str(chunk.get("file_path", ""))).name
        or ""
    ).strip()
    text = str(chunk.get("text", "")).strip()

    parts: List[str] = []
    if doc_name:
        parts.append(f"【来源文档】{doc_name}")
    if header_values:
        parts.append(f"【标题层级】{' > '.join(header_values)}")
    parts.append(text)
    return "\n".join(p for p in parts if p).strip()


def normalize_doc_name(doc: Any) -> str:
    if doc is None:
        return ""
    doc_str = str(doc).strip().lower()
    if not doc_str:
        return ""
    return Path(doc_str).name


def _strip_ext(name: str) -> str:
    return re.sub(r"\.(md|pdf|txt)$", "", name, flags=re.IGNORECASE).strip()


def _compact(name: str) -> str:
    # 统一去掉空白和常见分隔符，降低命名差异带来的误判。
    return re.sub(r"[\s_\-—–·()（）【】\[\]、，,。:：;；]+", "", name.lower())


def extract_doc_keys(doc: Any) -> set[str]:
    """
    从文档名中抽取稳定 key：
    1) 附件编号（如 附件1-10）
    2) 培养方案主键（如 大数据-2025级本科生培养方案-v13-724）
    3) 退化为去后缀 + 压缩后的全文名
    """
    if doc is None:
        return set()
    name = normalize_doc_name(doc)
    if not name:
        return set()

    base = _strip_ext(name)
    keys: set[str] = set()

    m = ATTACHMENT_KEY_RE.search(base)
    if m:
        keys.add(f"附件1-{int(m.group(1))}")

    m2 = PROGRAM_KEY_RE.search(base)
    if m2:
        keys.add(m2.group(1).lower())

    # fallback key
    keys.add(_compact(base))
    return keys


def _doc_name_fuzzy_match(gold_doc: str, chunk_doc: str) -> bool:
    gold_c = _compact(_strip_ext(normalize_doc_name(gold_doc)))
    chunk_c = _compact(_strip_ext(normalize_doc_name(chunk_doc)))
    if not gold_c or not chunk_c:
        return False
    return (gold_c in chunk_c) or (chunk_c in gold_c)


def ensure_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def page_to_int(page: Any) -> int | None:
    try:
        return int(page)
    except Exception:
        return None


def has_retrieval_label(sample: Dict[str, Any]) -> bool:
    return any(
        [
            sample.get("gold_chunk_id") not in (None, "", []),
            sample.get("gold_evidence_doc") not in (None, "", []),
            sample.get("gold_evidence_page") not in (None, "", []),
        ]
    )


def chunk_matches_gold(chunk: Dict[str, Any], sample: Dict[str, Any]) -> bool:
    gold_chunk_ids = [str(x) for x in ensure_list(sample.get("gold_chunk_id")) if str(x).strip()]
    if gold_chunk_ids:
        return str(chunk.get("chunk_id", "")) in gold_chunk_ids

    gold_docs = [normalize_doc_name(x) for x in ensure_list(sample.get("gold_evidence_doc")) if normalize_doc_name(x)]
    gold_pages = [page_to_int(x) for x in ensure_list(sample.get("gold_evidence_page")) if page_to_int(x) is not None]

    chunk_doc = normalize_doc_name(chunk.get("file_path"))
    chunk_page = page_to_int(chunk.get("page"))

    doc_ok = True
    if gold_docs:
        gold_keys: set[str] = set()
        for g in gold_docs:
            gold_keys.update(extract_doc_keys(g))

        chunk_keys: set[str] = set()
        chunk_keys.update(extract_doc_keys(chunk_doc))
        meta = chunk.get("metadata", {})
        if isinstance(meta, dict):
            for k in ("doc_name", "source_md", "source_pdf", "source", "file_path"):
                v = meta.get(k)
                if v:
                    chunk_keys.update(extract_doc_keys(v))

        # 先走稳定 key 命中，再走模糊兜底
        if gold_keys and chunk_keys:
            doc_ok = bool(gold_keys.intersection(chunk_keys))
        else:
            doc_ok = any(_doc_name_fuzzy_match(g, chunk_doc) for g in gold_docs)

    page_ok = True
    if gold_pages:
        page_ok = chunk_page in gold_pages

    return doc_ok and page_ok


def compute_retrieval_metrics_for_sample(
    ranked_chunks: List[Dict[str, Any]], sample: Dict[str, Any]
) -> Dict[str, Any]:
    if not has_retrieval_label(sample):
        return {
            "has_retrieval_label": 0,
            "retrieval_rank": np.nan,
            "hit@5": np.nan,
            "hit@10": np.nan,
            "mrr": np.nan,
        }

    rank = None
    for i, ch in enumerate(ranked_chunks, start=1):
        if chunk_matches_gold(ch, sample):
            rank = i
            break

    hit5 = 1.0 if rank is not None and rank <= 5 else 0.0
    hit10 = 1.0 if rank is not None and rank <= 10 else 0.0
    mrr = 1.0 / rank if rank else 0.0

    return {
        "has_retrieval_label": 1,
        "retrieval_rank": rank if rank is not None else np.nan,
        "hit@5": hit5,
        "hit@10": hit10,
        "mrr": mrr,
    }


def extract_citations(answer: str) -> List[int]:
    found = CITATION_RE.findall(answer or "")
    dedup: List[int] = []
    seen = set()
    for x in found:
        try:
            cid = int(x)
        except Exception:
            continue
        if cid not in seen:
            seen.add(cid)
            dedup.append(cid)
    return dedup


def compute_faithfulness(answer: str, contexts: List[Dict[str, Any]], no_answer_text: str) -> float:
    answer = (answer or "").strip()
    if not answer:
        return 0.0
    if answer == no_answer_text:
        return 1.0

    answer_tokens = set(tokenize_text(answer))
    if not answer_tokens:
        return 0.0

    context_text = "\n".join(c.get("text", "") for c in contexts)
    context_tokens = set(tokenize_text(context_text))
    if not context_tokens:
        return 0.0

    overlap = len(answer_tokens & context_tokens)
    return float(overlap / max(len(answer_tokens), 1))


def compute_citation_accuracy(
    answer: str,
    contexts: List[Dict[str, Any]],
    sample: Dict[str, Any],
) -> float:
    citations = extract_citations(answer)
    if not citations:
        return 0.0

    valid_count = 0
    relevant_count = 0
    for cid in citations:
        if 1 <= cid <= len(contexts):
            valid_count += 1
            if chunk_matches_gold(contexts[cid - 1], sample):
                relevant_count += 1

    if valid_count == 0:
        return 0.0

    if has_retrieval_label(sample):
        return float(relevant_count / valid_count)
    return float(valid_count / len(citations))


def compute_traceability(answer: str, contexts: List[Dict[str, Any]]) -> float:
    citations = extract_citations(answer)
    if not citations:
        return 0.0

    traceable = 0
    for cid in citations:
        if not (1 <= cid <= len(contexts)):
            continue
        c = contexts[cid - 1]
        file_path = str(c.get("file_path", "")).strip()
        page = c.get("page")
        if file_path and page not in (None, ""):
            traceable += 1

    return float(traceable / len(citations))


def to_compact_chunks(chunks: List[Dict[str, Any]], max_text_len: int = 160) -> str:
    rows = []
    for c in chunks:
        rows.append(
            {
                "chunk_id": c.get("chunk_id"),
                "file_path": c.get("file_path"),
                "page": c.get("page"),
                "dense_score": to_float(c.get("dense_score")),
                "rerank_score": to_float(c.get("rerank_score")),
                "text": str(c.get("text", ""))[:max_text_len],
            }
        )
    return json.dumps(rows, ensure_ascii=False)


def make_markdown_table(df: pd.DataFrame, float_digits: int = 4) -> str:
    if df.empty:
        return ""
    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, row in df.iterrows():
        vals = []
        for c in cols:
            v = row[c]
            if pd.isna(v):
                vals.append("")
            elif isinstance(v, (float, np.floating)):
                vals.append(f"{float(v):.{float_digits}f}")
            else:
                vals.append(str(v))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


class DenseRetriever:
    def __init__(self, model_name_or_path: str, device: str = "cpu", batch_size: int = 32):
        self.model_name_or_path = model_name_or_path
        self.batch_size = batch_size
        self.model = SentenceTransformer(model_name_or_path, device=device)
        self.corpus_chunks: List[Dict[str, Any]] = []
        self.corpus_emb: np.ndarray | None = None

    def build(self, chunks: List[Dict[str, Any]]) -> None:
        self.corpus_chunks = chunks
        texts = [build_embedding_text(c) for c in chunks]
        embs = self.model.encode(
            texts,
            batch_size=self.batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=True,
        )
        self.corpus_emb = np.asarray(embs, dtype=np.float32)

    def search(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        if self.corpus_emb is None:
            raise RuntimeError("DenseRetriever 尚未构建索引")

        q_emb = self.model.encode(
            [query],
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )[0].astype(np.float32)

        scores = np.dot(self.corpus_emb, q_emb)
        k = min(top_k, len(scores))
        top_idx = np.argpartition(-scores, kth=k - 1)[:k]
        top_idx = top_idx[np.argsort(-scores[top_idx])]

        results: List[Dict[str, Any]] = []
        for rank, idx in enumerate(top_idx, start=1):
            ch = dict(self.corpus_chunks[int(idx)])
            ch["dense_score"] = float(scores[int(idx)])
            ch["dense_rank"] = rank
            ch["chunk_index"] = int(idx)
            results.append(ch)
        return results

    def similarity(self, text_a: str, text_b: str) -> float:
        embs = self.model.encode(
            [text_a, text_b],
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        sim = float(np.dot(embs[0], embs[1]))
        return (sim + 1.0) / 2.0


class BGEReranker:
    def __init__(self, model_name_or_path: str, device: str = "cpu"):
        self.model = CrossEncoder(model_name_or_path, device=device)

    def rerank(self, query: str, candidates: List[Dict[str, Any]], top_k: int) -> List[Dict[str, Any]]:
        if not candidates:
            return []

        pairs = [[query, c.get("text", "")] for c in candidates]
        scores = self.model.predict(pairs, show_progress_bar=False)

        rescored = []
        for c, s in zip(candidates, scores):
            row = dict(c)
            row["rerank_score"] = float(s)
            rescored.append(row)

        rescored.sort(key=lambda x: x["rerank_score"], reverse=True)
        return rescored[: min(top_k, len(rescored))]


class KimiGenerator:
    def __init__(self, cfg: Dict[str, Any]):
        gen_cfg = cfg["generation"]
        self.base_url = str(gen_cfg["base_url"]).rstrip("/")
        self.model = gen_cfg["model"]
        self.temperature = float(gen_cfg.get("temperature", 0.1))
        self.max_tokens = int(gen_cfg.get("max_tokens", 512))
        self.timeout_sec = int(gen_cfg.get("timeout_sec", 60))
        self.no_answer_text = str(gen_cfg.get("no_answer_text", "未在材料中找到相关信息"))
        self.api_key = os.environ.get(gen_cfg.get("api_key_env", "KIMI_API_KEY"), "")

    def _build_system_prompt(self, system_id: str) -> str:
        base = (
            "你是工程教育认证私有知识助手。"
            "只能依据给定检索片段回答，不得编造，不得扩展外部知识。"
            "不要输出推理过程，不要展示思维链。"
        )
        if system_id == "S3":
            return (
                base
                + "每条关键事实后必须给出引用，格式为 [C1]、[C2]。"
                + f"若上下文不足以回答，必须且只能输出：{self.no_answer_text}。"
            )
        if system_id == "S2":
            return base + "请尽量给出引用标记 [Ck]。"
        return base

    @staticmethod
    def _format_contexts(contexts: List[Dict[str, Any]]) -> str:
        lines: List[str] = []
        for i, c in enumerate(contexts, start=1):
            file_path = c.get("file_path", "")
            page = c.get("page", "")
            text = c.get("text", "")
            lines.append(f"[C{i}] file_path={file_path} | page={page}\n{text}")
        return "\n\n".join(lines)

    def _offline_answer(self, query: str, contexts: List[Dict[str, Any]], system_id: str) -> str:
        if not contexts:
            return self.no_answer_text
        c1 = contexts[0].get("text", "")
        c1 = str(c1)[:220]
        if system_id == "S3":
            return f"{c1} [C1]"
        return c1

    def generate(self, query: str, contexts: List[Dict[str, Any]], system_id: str) -> str:
        if not self.api_key:
            logging.warning("未检测到 KIMI_API_KEY，使用离线回退回答")
            return self._offline_answer(query, contexts, system_id)

        system_prompt = self._build_system_prompt(system_id)
        user_prompt = (
            "以下是检索片段，请基于这些材料回答问题。\n"
            f"问题：{query}\n\n"
            "检索片段：\n"
            f"{self._format_contexts(contexts)}\n\n"
            "请直接给出最终答案。"
        )

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=self.timeout_sec,
            )
            response.raise_for_status()
            data = response.json()
            return (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
                or self.no_answer_text
            )
        except Exception as exc:
            logging.exception("Kimi API 调用失败: %s", exc)
            return self.no_answer_text


def run_dense_only(
    sample: Dict[str, Any],
    retriever: DenseRetriever,
    generator: KimiGenerator,
    cfg: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], str]:
    dense = retriever.search(sample["query"], int(cfg["retrieval"]["top_k_dense"]))
    contexts = dense[: int(cfg["retrieval"]["top_k_context"])]
    answer = generator.generate(sample["query"], contexts, system_id="S1")
    return dense, [], contexts, answer


def run_with_rerank(
    sample: Dict[str, Any],
    retriever: DenseRetriever,
    reranker: BGEReranker,
    generator: KimiGenerator,
    cfg: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], str]:
    dense = retriever.search(sample["query"], int(cfg["retrieval"]["top_k_dense"]))
    reranked = reranker.rerank(sample["query"], dense, int(cfg["retrieval"]["top_k_rerank"]))
    contexts = reranked[: int(cfg["retrieval"]["top_k_context"])]
    answer = generator.generate(sample["query"], contexts, system_id="S2")
    return dense, reranked, contexts, answer


def run_full_pipeline(
    sample: Dict[str, Any],
    retriever: DenseRetriever,
    reranker: BGEReranker,
    generator: KimiGenerator,
    cfg: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], str]:
    dense = retriever.search(sample["query"], int(cfg["retrieval"]["top_k_dense"]))
    reranked = reranker.rerank(sample["query"], dense, int(cfg["retrieval"]["top_k_rerank"]))
    contexts = reranked[: int(cfg["retrieval"]["top_k_context"])]
    answer = generator.generate(sample["query"], contexts, system_id="S3")
    return dense, reranked, contexts, answer


def generate_reports(
    summary_df: pd.DataFrame,
    retrieval_df: pd.DataFrame,
    generation_df: pd.DataFrame,
    cfg: Dict[str, Any],
) -> None:
    out = cfg["output"]

    sys_desc = pd.DataFrame(
        [
            {
                "system": sid,
                "system_name": SYSTEM_META[sid]["name"],
                "dense_retrieval": SYSTEM_META[sid]["dense"],
                "reranker": SYSTEM_META[sid]["rerank"],
                "constrained_prompt": SYSTEM_META[sid]["constrained_prompt"],
            }
            for sid in cfg["systems"]
            if sid in SYSTEM_META
        ]
    )

    summary_md = []
    summary_md.append("# 第五章实验结果汇总\n")
    summary_md.append("## 1. 系统配置\n")
    summary_md.append(make_markdown_table(sys_desc))
    summary_md.append("\n## 2. 检索性能\n")
    summary_md.append(make_markdown_table(retrieval_df))
    summary_md.append("\n## 3. 生成质量与证据链\n")
    summary_md.append(make_markdown_table(generation_df))

    save_text(Path(out["chapter5_result_summary_md"]), "\n".join(summary_md))

    obs = []
    obs.append("# 第五章实验观察\n")
    if not summary_df.empty:
        def _get(system: str, col: str) -> float | None:
            row = summary_df[summary_df["system"] == system]
            if row.empty:
                return None
            val = row.iloc[0].get(col)
            if pd.isna(val):
                return None
            return float(val)

        s1_mrr = _get("S1", "MRR")
        s2_mrr = _get("S2", "MRR")
        s2_faith = _get("S2", "Faithfulness")
        s3_faith = _get("S3", "Faithfulness")
        s2_cite = _get("S2", "Citation Accuracy")
        s3_cite = _get("S3", "Citation Accuracy")
        s2_trace = _get("S2", "Traceability Success Rate")
        s3_trace = _get("S3", "Traceability Success Rate")

        if s1_mrr is not None and s2_mrr is not None:
            obs.append(f"- S2 相比 S1 的 MRR 变化为 {s2_mrr - s1_mrr:+.4f}。")
        if s2_faith is not None and s3_faith is not None:
            obs.append(f"- S3 相比 S2 的 Faithfulness 变化为 {s3_faith - s2_faith:+.4f}。")
        if s2_cite is not None and s3_cite is not None:
            obs.append(f"- S3 相比 S2 的 Citation Accuracy 变化为 {s3_cite - s2_cite:+.4f}。")
        if s2_trace is not None and s3_trace is not None:
            obs.append(f"- S3 相比 S2 的 Traceability Success Rate 变化为 {s3_trace - s2_trace:+.4f}。")

    if len(obs) == 1:
        obs.append("- 当前数据不足以形成稳定结论，建议扩大测试样本并补齐证据标注。")

    save_text(Path(out["chapter5_observations_md"]), "\n".join(obs) + "\n")


def run_eval(cfg: Dict[str, Any]) -> None:
    t0 = time.time()

    test_path = Path(cfg["data"]["test_queries_path"])
    corpus_path = Path(cfg["data"]["corpus_chunks_path"])

    test_samples = load_test_queries(test_path)
    corpus_chunks = load_corpus_chunks(corpus_path)

    max_samples = cfg.get("runtime", {}).get("max_samples")
    if isinstance(max_samples, int) and max_samples > 0:
        test_samples = test_samples[:max_samples]

    logging.info("测试问题数: %d", len(test_samples))
    logging.info("语料 chunk 数: %d", len(corpus_chunks))

    retriever = DenseRetriever(
        cfg["models"]["dense_model_name_or_path"],
        device=str(cfg["runtime"].get("device", "cpu")),
        batch_size=int(cfg["runtime"].get("batch_size", 32)),
    )
    retriever.build(corpus_chunks)

    reranker = None
    if any(s in ["S2", "S3"] for s in cfg["systems"]):
        reranker = BGEReranker(
            cfg["models"]["reranker_model_name_or_path"],
            device=str(cfg["runtime"].get("device", "cpu")),
        )

    generator = KimiGenerator(cfg)
    no_answer_text = cfg["generation"].get("no_answer_text", "未在材料中找到相关信息")

    rows: List[Dict[str, Any]] = []

    for system_id in cfg["systems"]:
        if system_id not in SYSTEM_META:
            logging.warning("跳过未知系统配置: %s", system_id)
            continue

        logging.info("开始评测系统: %s", system_id)
        for i, sample in enumerate(test_samples, start=1):
            query_id = sample["id"]
            query = sample["query"]

            logging.info("[%s] 处理样本 %d/%d | %s", system_id, i, len(test_samples), query_id)

            dense_chunks: List[Dict[str, Any]] = []
            rerank_chunks: List[Dict[str, Any]] = []
            contexts: List[Dict[str, Any]] = []
            answer = ""
            error_msg = ""

            try:
                if system_id == "S1":
                    dense_chunks, rerank_chunks, contexts, answer = run_dense_only(
                        sample, retriever, generator, cfg
                    )
                    retrieval_for_eval = dense_chunks
                elif system_id == "S2":
                    if reranker is None:
                        raise RuntimeError("S2 需要 reranker，但未初始化")
                    dense_chunks, rerank_chunks, contexts, answer = run_with_rerank(
                        sample, retriever, reranker, generator, cfg
                    )
                    retrieval_for_eval = rerank_chunks
                elif system_id == "S3":
                    if reranker is None:
                        raise RuntimeError("S3 需要 reranker，但未初始化")
                    dense_chunks, rerank_chunks, contexts, answer = run_full_pipeline(
                        sample, retriever, reranker, generator, cfg
                    )
                    retrieval_for_eval = rerank_chunks
                else:
                    raise ValueError(f"未知系统: {system_id}")

                retrieval_metrics = compute_retrieval_metrics_for_sample(retrieval_for_eval, sample)
                faithfulness = compute_faithfulness(answer, contexts, no_answer_text)
                answer_relevance = retriever.similarity(query, answer) if answer else 0.0
                citation_acc = compute_citation_accuracy(answer, contexts, sample)
                traceability = compute_traceability(answer, contexts)

                if i <= 3:
                    top1_doc = Path(str((retrieval_for_eval or [{}])[0].get("file_path", ""))).name
                    logging.info(
                        "[%s][%s] top1=%s rank=%s hit@5=%s",
                        system_id,
                        query_id,
                        top1_doc,
                        retrieval_metrics.get("retrieval_rank"),
                        retrieval_metrics.get("hit@5"),
                    )

            except Exception as exc:
                logging.exception("样本处理失败 | system=%s query_id=%s", system_id, query_id)
                error_msg = str(exc)
                retrieval_metrics = {
                    "has_retrieval_label": 1 if has_retrieval_label(sample) else 0,
                    "retrieval_rank": np.nan,
                    "hit@5": 0.0,
                    "hit@10": 0.0,
                    "mrr": 0.0,
                }
                faithfulness = 0.0
                answer_relevance = 0.0
                citation_acc = 0.0
                traceability = 0.0
                answer = no_answer_text

            row = {
                "system": system_id,
                "system_name": SYSTEM_META[system_id]["name"],
                "query_id": query_id,
                "query": query,
                "question_type": sample.get("question_type", ""),
                "gold_answer": sample.get("gold_answer", ""),
                "gold_evidence_doc": json.dumps(ensure_list(sample.get("gold_evidence_doc")), ensure_ascii=False),
                "gold_evidence_page": json.dumps(ensure_list(sample.get("gold_evidence_page")), ensure_ascii=False),
                "answer": answer,
                "citations": json.dumps(extract_citations(answer), ensure_ascii=False),
                "dense_chunks": to_compact_chunks(dense_chunks),
                "reranked_chunks": to_compact_chunks(rerank_chunks),
                "used_context_chunks": to_compact_chunks(contexts),
                "has_retrieval_label": retrieval_metrics["has_retrieval_label"],
                "retrieval_rank": retrieval_metrics["retrieval_rank"],
                "hit@5": retrieval_metrics["hit@5"],
                "hit@10": retrieval_metrics["hit@10"],
                "mrr": retrieval_metrics["mrr"],
                "faithfulness": faithfulness,
                "answer_relevance": answer_relevance,
                "citation_accuracy": citation_acc,
                "traceability_success_rate": traceability,
                "error": error_msg,
            }
            rows.append(row)

    detailed_df = pd.DataFrame(rows)

    out_cfg = cfg["output"]
    detailed_path = Path(out_cfg["detailed_results_csv"])
    ensure_parent(detailed_path)
    detailed_df.to_csv(detailed_path, index=False, encoding="utf-8-sig")

    retrieval_summary = (
        detailed_df.groupby("system", dropna=False)
        .agg(
            samples=("query_id", "count"),
            labeled_samples=("has_retrieval_label", "sum"),
            Hit_at_5=("hit@5", "mean"),
            Hit_at_10=("hit@10", "mean"),
            MRR=("mrr", "mean"),
        )
        .reset_index()
    )

    generation_summary = (
        detailed_df.groupby("system", dropna=False)
        .agg(
            samples=("query_id", "count"),
            Faithfulness=("faithfulness", "mean"),
            Answer_Relevance=("answer_relevance", "mean"),
            Citation_Accuracy=("citation_accuracy", "mean"),
            Traceability_Success_Rate=("traceability_success_rate", "mean"),
        )
        .reset_index()
    )

    summary_df = retrieval_summary.merge(generation_summary, on=["system", "samples"], how="outer")

    retrieval_results = retrieval_summary.rename(
        columns={"Hit_at_5": "Hit@5", "Hit_at_10": "Hit@10"}
    )
    generation_results = generation_summary.rename(
        columns={
            "Answer_Relevance": "Answer Relevance",
            "Citation_Accuracy": "Citation Accuracy",
            "Traceability_Success_Rate": "Traceability Success Rate",
        }
    )

    summary_results = summary_df.rename(
        columns={
            "Hit_at_5": "Hit@5",
            "Hit_at_10": "Hit@10",
            "Answer_Relevance": "Answer Relevance",
            "Citation_Accuracy": "Citation Accuracy",
            "Traceability_Success_Rate": "Traceability Success Rate",
        }
    )

    retrieval_path = Path(out_cfg["retrieval_results_csv"])
    generation_path = Path(out_cfg["generation_results_csv"])
    summary_path = Path(out_cfg["summary_results_csv"])

    ensure_parent(retrieval_path)
    ensure_parent(generation_path)
    ensure_parent(summary_path)

    retrieval_results.to_csv(retrieval_path, index=False, encoding="utf-8-sig")
    generation_results.to_csv(generation_path, index=False, encoding="utf-8-sig")
    summary_results.to_csv(summary_path, index=False, encoding="utf-8-sig")

    generate_reports(summary_results, retrieval_results, generation_results, cfg)

    elapsed = time.time() - t0
    logging.info("评测完成，用时 %.2fs", elapsed)
    logging.info("输出文件: %s", detailed_path)
    logging.info("输出文件: %s", summary_path)
    logging.info("输出文件: %s", retrieval_path)
    logging.info("输出文件: %s", generation_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="端到端 RAG 系统评测")
    parser.add_argument(
        "--config",
        type=str,
        default="experiments/end2end/configs/eval_config.yaml",
        help="评测配置文件路径",
    )
    parser.add_argument(
        "--systems",
        type=str,
        default="",
        help="可选：仅运行指定系统，例如 S1,S3",
    )
    parser.add_argument(
        "--max-samples",
        type=int,
        default=0,
        help="可选：仅运行前N条样本用于快速验证，0表示全量。",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cfg_path = Path(args.config)
    cfg = load_yaml(cfg_path)

    if args.systems.strip():
        cfg["systems"] = [s.strip() for s in args.systems.split(",") if s.strip()]
    if args.max_samples and args.max_samples > 0:
        cfg.setdefault("runtime", {})
        cfg["runtime"]["max_samples"] = int(args.max_samples)

    log_file = Path(cfg["logging"]["log_file"])
    setup_logging(log_file=log_file, level=str(cfg["logging"].get("level", "INFO")))

    try:
        run_eval(cfg)
    except Exception:
        logging.exception("评测主流程失败")
        raise


if __name__ == "__main__":
    main()
