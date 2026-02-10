"""基于 BGEEmbedding 封装类的新版向量库构建脚本。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Generator, Iterable, List, Sequence

from langchain_chroma import Chroma

# 1. 设置路径
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

# 导入你刚刚修改好的类
from embeddings.bge_embedding import BGEEmbedding 

class _LCEmbeddingAdapter:
    """
    适配器：将你的 BGEEmbedding 类转为 LangChain Chroma 所需的标准接口。
    """
    def __init__(self, embedder: BGEEmbedding) -> None:
        # 直接使用你类中封装好的 LangChain 对象
        self.lc_embeddings = embedder._embeddings

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self.lc_embeddings.embed_documents(texts)

    def embed_query(self, text: str) -> List[float]:
        return self.lc_embeddings.embed_query(text)

def load_chunks(jsonl_path: Path) -> Generator[Dict[str, object], None, None]:
    if not jsonl_path.exists():
        raise FileNotFoundError(f"找不到 chunk 文件: {jsonl_path}")
    with jsonl_path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip(): continue
            yield json.loads(line)

def to_batches(items: Iterable[Dict[str, object]], batch_size: int):
    batch = []
    for item in items:
        batch.append(item)
        if len(batch) >= batch_size:
            yield batch
            batch = []
    if batch:
        yield batch

def _normalize_metadata(value: object):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return ", ".join(str(i) for i in value)
    return str(value)

def build_metadata(chunk: Dict[str, object]) -> Dict[str, object]:
    extra = chunk.get("metadata", {})
    meta = {
        "chunk_id": chunk.get("chunk_id"),
        "source": extra.get("source"),
        "page_labels": extra.get("page_labels"),
        "headers": extra.get("headers"), 
        "category": extra.get("category", "programs")
    }
    return {k: _normalize_metadata(v) for k, v in meta.items()}

def run_pipeline(
    jsonl_path: Path,
    persist_dir: Path,
    batch_size: int,
    collection_name: str
) -> None:
    # 🌟 初始化你新修改的 BGE 类
    print(f"⏳ 正在初始化 BGE-M3 模型 (Batch Size: {batch_size})...")
    bge_model = BGEEmbedding(
        model_name="e:/rag-project/models/bge-m3", 
        batch_size=batch_size
    )
    
    # 使用适配器连接 Chroma
    adapter = _LCEmbeddingAdapter(bge_model)
    
    persist_dir.mkdir(parents=True, exist_ok=True)
    vector_store = Chroma(
        collection_name=collection_name,
        embedding_function=adapter,
        persist_directory=str(persist_dir),
    )

    print(f"🚀 开始写入新库: {persist_dir.name}")
    total_added = 0
    
    for batch in to_batches(load_chunks(jsonl_path), batch_size):
        ids, texts, metadatas = [], [], []
        for item in batch:
            text = (item.get("text") or "").strip()
            if not text: continue
            
            ids.append(str(item.get("chunk_id")))
            texts.append(text)
            metadatas.append(build_metadata(item))
            
        if texts:
            vector_store.add_texts(texts=texts, metadatas=metadatas, ids=ids)
            total_added += len(texts)
            print(f"已处理: {total_added} 条...")

    print("-" * 50)
    print(f"✅ 构建完成！存储路径: {persist_dir}")

if __name__ == "__main__":
    # 配置
    INPUT_FILE = PROJECT_ROOT / "data" / "chunks" / "all_chunks.jsonl"
    NEW_DB_PATH = PROJECT_ROOT / "data" / "chroma" / "bge_v2_db"
    
    run_pipeline(
        jsonl_path=INPUT_FILE,
        persist_dir=NEW_DB_PATH,
        batch_size=32,  # BGE 模型可以设大一点，加快速度
        collection_name="bge_collection"
    )