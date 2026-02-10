"""基于 LangChain 的 QZhou-Embedding + Chroma 构建脚本。"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Dict, Generator, Iterable, List, Optional, Sequence

try:
    from langchain_chroma import Chroma
except ImportError:
    from langchain_community.vectorstores import Chroma

# 1. 修正路径逻辑：脚本在 scripts/ 下，向上跳两级到达根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

# 导入你刚刚修改过的 QZhouEmbedding 类

from embeddings.QZhou_Zh_embedding import QZhouEmbedding 

class _LCEmbeddingAdapter:
    """将 QZhouEmbedding 适配为 LangChain 所需接口。"""

    def __init__(self, embedder: QZhouEmbedding) -> None:
        self.embedder = embedder

    def embed_documents(self, texts: Sequence[str]) -> List[List[float]]:
        """嵌入多条文档。"""
        # 过滤 None 并获取向量
        embeddings = self.embedder.embed_texts(texts)
        return [vec for vec in embeddings if vec is not None]

    def embed_query(self, text: str) -> List[float]:
        """嵌入单条查询。"""
        embedding = self.embedder.embed_text(text)
        return embedding or []

def load_chunks(jsonl_path: Path) -> Generator[Dict[str, object], None, None]:
    """逐行读取 chunk jsonl。"""
    if not jsonl_path.exists():
        raise FileNotFoundError(f"找不到 chunk 文件: {jsonl_path}")
    
    with jsonl_path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip(): continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue

def to_batches(items: Iterable[Dict[str, object]], batch_size: int) -> Generator[List[Dict[str, object]], None, None]:
    """将数据分批，适配大模型显存限制。"""
    batch: List[Dict[str, object]] = []
    for item in items:
        batch.append(item)
        if len(batch) >= batch_size:
            yield batch
            batch = []
    if batch:
        yield batch

def _normalize_metadata_value(value: object) -> str | int | float | bool | None:
    """将元数据（如 page_labels 列表）转为 Chroma 支持的标量或字符串。"""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    # Chroma 不支持 List 类型作为元数据值，需转为逗号分隔的字符串
    if isinstance(value, (list, tuple)):
        return ", ".join(str(i) for i in value)
    return str(value)

def build_metadata(chunk: Dict[str, object]) -> Dict[str, object]:
    """提取并规范化元数据，保留页码和类别信息。"""
    # 提取 chunk 内部的 metadata 字典
    extra = chunk.get("metadata", {})
    
    # 构造要存入向量库的平铺元数据
    meta = {
        "chunk_id": chunk.get("chunk_id"),
        "source": extra.get("source"),
        "category": extra.get("category", "general"),
        "page_labels": extra.get("page_labels"),  # 关键：溯源页码 
        "is_cross_page": extra.get("is_cross_page"),
    }
    
    # 规范化处理
    return {k: _normalize_metadata_value(v) for k, v in meta.items()}

def prepare_entries(batch: Sequence[Dict[str, object]]) -> tuple[List[str], List[str], List[Dict[str, object]]]:
    """准备写入 Chroma 的三要素：IDs, Texts, Metadatas。"""
    ids, texts, metadatas = [], [], []
    for item in batch:
        text = (item.get("text") or "").strip()
        if not text: 
            print(f"⚠️ 跳过空分块: {item.get('chunk_id')}")
            continue
        
        ids.append(str(item.get("chunk_id")))
        texts.append(text)
        metadatas.append(build_metadata(item))
    return ids, texts, metadatas

def run_pipeline(
    jsonl_path: Path,
    persist_dir: Path,
    batch_size: int,
    reset: bool,
    collection_name: str = "qzhou_7b_chunks",
) -> None:
    """执行完整的入库流程。"""
    if reset and persist_dir.exists():
        print(f"🗑️ 正在清空旧的向量库: {persist_dir}")
        shutil.rmtree(persist_dir)

    # 初始化新模型 (7B 模型)
    embedder = QZhouEmbedding(batch_size=batch_size) 
    adapter = _LCEmbeddingAdapter(embedder)
    
    persist_dir.mkdir(parents=True, exist_ok=True)
    vector_store = Chroma(
        collection_name=collection_name,
        embedding_function=adapter,
        persist_directory=str(persist_dir),
    )

    print(f"🚀 开始处理数据: {jsonl_path.name}")
    total_added = 0
    
    for batch in to_batches(load_chunks(jsonl_path), batch_size):
        ids, texts, metadatas = prepare_entries(batch)
        if not texts: continue
        
        vector_store.add_texts(texts=texts, metadatas=metadatas, ids=ids)
        total_added += len(texts)
        print(f"已写入: {total_added} 条...")

    print("-" * 50)
    print(f"✅ 任务完成！")
    print(f"📊 存储总量: {total_added} 条分块")
    print(f"💾 数据库路径: {persist_dir.relative_to(PROJECT_ROOT)}")

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="批量将工程认证 Chunk 写入 Chroma。")
    parser.add_argument("--input", type=Path, default=PROJECT_ROOT / "data" / "chunks" / "all_chunks.jsonl")
    parser.add_argument("--persist-dir", type=Path, default=PROJECT_ROOT / "data" / "chroma" / "qzhou_7b_db")
    # ⚠️ 对于 7B 模型，写入 batch 不宜过大，防止显存溢出
    parser.add_argument("--batch-size", type=int, default=4) 
    parser.add_argument("--reset", action="store_true", help="清空库并重新开始")
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    run_pipeline(
        jsonl_path=args.input,
        persist_dir=args.persist_dir,
        batch_size=args.batch_size,
        reset=args.reset,
    )