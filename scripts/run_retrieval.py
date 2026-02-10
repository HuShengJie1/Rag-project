"""纯检索验证脚本：从本地 Chroma 向量库检索文本 chunk。"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import List




# from langchain_community.vectorstores import Chroma
from langchain_chroma import Chroma
# 将 src 加入搜索路径，便于导入已有 embedding 模块
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from embeddings.bge_embedding import BGEEmbedding  # noqa: E402
from embeddings.QZhou_Zh_embedding import QZhouEmbedding

class _LCEmbeddingAdapter:
    """将 BGEEmbedding 适配为 LangChain 所需接口。"""

    # def __init__(self, embedder: BGEEmbedding) -> None:
    #     self.embedder = embedder
        
    def __init__(self, embedder: BGEEmbedding) -> None:
        self.embedder = embedder

    def embed_query(self, text: str) -> List[float]:
        """嵌入单条查询。"""
        embedding = self.embedder.embed_text(text)
        return embedding or []

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """嵌入多条文档。"""
        return [vec for vec in self.embedder.embed_texts(texts) if vec is not None]


def init_vector_store(persist_dir: Path, collection_name: str, adapter: _LCEmbeddingAdapter) -> Chroma:
    """以只读方式连接本地 Chroma 向量库。"""
    if not persist_dir.exists():
        raise FileNotFoundError(f"向量库目录不存在: {persist_dir}")
    return Chroma(
        collection_name=collection_name,
        embedding_function=adapter,
        persist_directory=str(persist_dir),
    )


def _preview_text(text: str, limit: int) -> str:
    """截断文本，避免终端输出过长。"""
    cleaned = text.replace("\n", " ").strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[:limit] + "..."


def run_retrieval(
    query: str,
    persist_dir: Path,
    collection_name: str,
    top_k: int,
    preview_len: int,
) -> None:
    """执行相似度检索并打印结果。"""
    embedder = BGEEmbedding()
    adapter = _LCEmbeddingAdapter(embedder)
    vector_store = init_vector_store(persist_dir, collection_name, adapter)

    results = vector_store.similarity_search(query, k=top_k)
    if not results:
        print("未检索到结果。")
        return

    for idx, doc in enumerate(results, start=1):
        metadata = doc.metadata or {}
        chunk_id = metadata.get("chunk_id", "")
        source_file = metadata.get("source", "")
        source_type = metadata.get("category", "")
        page_labels = metadata.get("page_labels")
        text_preview = _preview_text(doc.page_content or "", preview_len)

        print(f"[{idx}] chunk_id: {chunk_id}")
        print(f"    source: {source_file}")
        print(f"    source_type: {source_type}")
        print(f"    page_labels: {page_labels}")
        print(f"    text: {text_preview}")


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(description="纯检索验证脚本（Chroma + BGEEmbedding）。")
    parser.add_argument(
        "--query",
        type=str,
        default="大数据专业的学科基础课",
        help="检索查询字符串",
    )
    parser.add_argument(
        "--persist-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "chroma" / "bge_v2_db",
        help="Chroma 持久化目录",
    )
    parser.add_argument(
        "--collection-name",
        type=str,
        default="bge_collection",
        help="向量集合名称",
    )
    parser.add_argument("--top-k", type=int, default=20, help="返回的相似度结果数量")
    parser.add_argument("--preview-len", type=int, default=2000000, help="文本预览长度上限")
    return parser.parse_args()


def main() -> None:
    """命令行入口。"""
    args = parse_args()
    run_retrieval(
        query=args.query,
        persist_dir=args.persist_dir,
        collection_name=args.collection_name,
        top_k=args.top_k,
        preview_len=args.preview_len,
    )


if __name__ == "__main__":
    main()
