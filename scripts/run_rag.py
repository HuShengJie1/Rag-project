"""最小 RAG 执行脚本：Chroma 检索 + LLM 生成。"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

try:
    from langchain_chroma import Chroma
except ImportError:  # pragma: no cover - fallback for older installs
    from langchain_chroma import Chroma

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from embeddings.bge_embedding import BGEEmbedding  # noqa: E402
from embeddings.QZhou_Zh_embedding import QZhouEmbedding

PERSIST_DIR = PROJECT_ROOT / "data" / "chroma" / "qzhou_7b_db"
COLLECTION_NAME = "qzhou_7b_chunks"
DEFAULT_NO_EVIDENCE = "未在材料中找到依据"


class _LCEmbeddingAdapter:
    """将 BGEEmbedding 适配为 LangChain 所需接口。"""

    # def __init__(self, embedder: BGEEmbedding) -> None:
    #     self.embedder = embedder

    def __init__(self, embedder: QZhouEmbedding) -> None:
        self.embedder = embedder
    
    def embed_query(self, text: str) -> List[float]:
        embedding = self.embedder.embed_text(text)
        return embedding or []

    def embed_documents(self, texts: Sequence[str]) -> List[List[float]]:
        return [vec for vec in self.embedder.embed_texts(texts) if vec is not None]


def init_vector_store(persist_dir: Path, collection_name: str, adapter: _LCEmbeddingAdapter) -> Chroma:
    if not persist_dir.exists():
        raise FileNotFoundError(f"向量库目录不存在: {persist_dir}")
    return Chroma(
        collection_name=collection_name,
        embedding_function=adapter,
        persist_directory=str(persist_dir),
    )


def _preview_text(text: str, limit: int) -> str:
    cleaned = text.replace("\n", " ").strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[:limit] + "..."


def _extract_chunk_id(metadata: Dict[str, Any]) -> str:
    chunk_id = metadata.get("chunk_id") or metadata.get("id") or ""
    return str(chunk_id) if chunk_id is not None else ""


def retrieve_chunks(
    vector_store: Chroma,
    query: str,
    top_k: int,
    preview_len: int,
) -> Tuple[List[str], List[Dict[str, Any]], str]:
    results = vector_store.similarity_search_with_score(query, k=top_k)
    if not results:
        return [], [], ""
    
    evidence: List[str] = []
    retrieved: List[Dict[str, Any]] = []
    contexts: List[str] = []

    for rank, (doc, score) in enumerate(results, start=1):
        metadata = doc.metadata or {}
        chunk_id = _extract_chunk_id(metadata)
        if chunk_id:
            evidence.append(chunk_id)
        contexts.append(doc.page_content or "")

        retrieved.append(
            {
                "rank": rank,
                "chunk_id": chunk_id,
                "score": float(score) if score is not None else None,
                "preview": _preview_text(doc.page_content or "", preview_len),
                "metadata": metadata,
            }
        )
    
    context = "\n\n".join(text for text in contexts if text.strip())
    return evidence, retrieved, context


def build_messages(context: str, query: str) -> List[Any]:
    system_text = (
        "你是一个严格的检索问答助手，只能依据提供的材料作答。"
        "如果材料不足以回答问题，请只回复“未在材料中找到依据”。"
        "不要使用外部知识，不要编造。"
    )
    user_text = f"材料：\n{context}\n\n问题：{query}\n\n请基于材料作答："
    return [SystemMessage(content=system_text), HumanMessage(content=user_text)]


def get_llm(provider: str, model: str) -> ChatOpenAI:
    if provider == "openai":
        return ChatOpenAI(model=model, temperature=0, api_key=os.getenv("OPENAI_API_KEY"))
    if provider == "deepseek":
        base_url = "https://api.deepseek.com"
        return ChatOpenAI(
            model=model,
            temperature=0.7,
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url=base_url,
        )
    raise ValueError(f"未知 provider: {provider}")


def resolve_default_model(provider: str, user_model: Optional[str]) -> str:
    if user_model:
        return user_model
    if provider == "deepseek":
        return "deepseek-chat"
    return "gpt-4o-mini"


def output_result(
    answer: str,
    evidence: List[str],
    retrieved: Optional[List[Dict[str, Any]]],
    json_mode: bool,
) -> None:
    if json_mode:
        payload: Dict[str, Any] = {"answer": answer, "evidence": evidence}
        if retrieved is not None:
            payload["retrieved"] = retrieved
        print(json.dumps(payload, ensure_ascii=False))
        return

    print(f"Answer: {answer}")
    print(f"Evidence: {json.dumps(evidence, ensure_ascii=False)}")
    if retrieved is not None:
        print(f"Retrieved: {json.dumps(retrieved, ensure_ascii=False)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="最小 RAG 执行脚本（Chroma + BGEEmbedding + LLM）。")
    parser.add_argument("--query", type=str, default="毕业学分要求", help="用户问题")
    parser.add_argument("--top-k", type=int, default=5, help="检索 chunk 数量")
    parser.add_argument("--provider", type=str, choices=["openai", "deepseek"], default="deepseek", help="LLM 提供方")
    parser.add_argument("--model", type=str, default="deepseek-chat", help="模型名")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出结果")
    parser.add_argument("--debug", action="store_true", help="输出检索详情")
    parser.add_argument("--preview-len", type=int, default=200, help="debug 预览长度")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    try:
        embedder = QZhouEmbedding()
        adapter = _LCEmbeddingAdapter(embedder)
        vector_store = init_vector_store(PERSIST_DIR, COLLECTION_NAME, adapter)

        evidence, retrieved, context = retrieve_chunks(
            vector_store=vector_store,
            query=args.query,
            top_k=args.top_k,
            preview_len=args.preview_len,
        )

        if not context.strip():
            answer = DEFAULT_NO_EVIDENCE
        else:
            llm = get_llm(args.provider, resolve_default_model(args.provider, args.model))
            messages = build_messages(context=context, query=args.query)
            response = llm.invoke(messages)
            answer = (response.content or "").strip() or DEFAULT_NO_EVIDENCE

        output_result(
            answer=answer,
            evidence=evidence,
            retrieved=retrieved if args.debug else None,
            json_mode=args.json,
        )
    except Exception as exc:  # pragma: no cover - 交给调用方处理
        sys.stderr.write(f"ERROR: {exc}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
