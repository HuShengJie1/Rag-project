"""基于 LangChain 的 BGE-M3 文本向量化封装。"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple
import os
from pathlib import Path
import torch
from langchain_huggingface.embeddings import HuggingFaceEmbeddings as _HuggingFaceEmbeddings

class BGEEmbedding:
    """
    使用 HuggingFaceEmbeddings 加载 BAAI/bge-m3 模型。
    BGE-M3 支持多语言、8192 长度上下文，且在处理结构化表格数据时具有极强的鲁棒性。
    """

    _MODEL_CACHE: Dict[Tuple[str, Optional[str]], _HuggingFaceEmbeddings] = {}

    def __init__(
        self,
        # 默认路径
        model_name: Optional[str] = None,
        device: Optional[str] = None,
        batch_size: int = 32,  
        normalize_embeddings: bool = True,
    ) -> None:
        """
        初始化 BGE 向量模型。
        """
        # 自动检测设备
        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
            
        if model_name is None:
            project_root = Path(__file__).resolve().parents[2]
            default_path = project_root / "models" / "bge-m3"
            model_name = os.getenv("BGE_M3_PATH", str(default_path))

        cache_key = (model_name, device)
        if cache_key not in self._MODEL_CACHE:
            model_kwargs = {
                "device": device,
                "trust_remote_code": True,
                "model_kwargs": {"torch_dtype": torch.float16 if device == "cuda" else torch.float32}
            }
            encode_kwargs = {
                "batch_size": batch_size, 
                "normalize_embeddings": normalize_embeddings
            }
            
            print(f"🚀 正在加载 BGE-M3 模型 {model_name} 到 {device}...")
            self._MODEL_CACHE[cache_key] = _HuggingFaceEmbeddings(
                model_name=model_name,
                model_kwargs=model_kwargs,
                encode_kwargs=encode_kwargs,
            )
            
        self._embeddings = self._MODEL_CACHE[cache_key]

    def _filter_texts(self, texts: Sequence[Optional[str]]) -> Tuple[List[str], List[int]]:
        """过滤空字符串，防止向量化报错。"""
        valid_texts: List[str] = []
        indices: List[int] = []
        for idx, text in enumerate(texts):
            if text is None:
                continue
            cleaned = text.strip()
            if not cleaned:
                continue
            valid_texts.append(cleaned)
            indices.append(idx)
        return valid_texts, indices

    def embed_texts(self, texts: Sequence[Optional[str]]) -> List[Optional[List[float]]]:
        """批量生成文本向量。"""
        if not texts:
            return []

        results: List[Optional[List[float]]] = [None] * len(texts)
        valid_texts, indices = self._filter_texts(texts)
        if not valid_texts:
            return results

        # 调用底层的 embed_documents
        embeddings = self._embeddings.embed_documents(valid_texts)
        
        for emb, idx in zip(embeddings, indices):
            results[idx] = list(emb)
        return results

    def embed_text(self, text: Optional[str]) -> Optional[List[float]]:
        """单条文本向量化。"""
        batch = self.embed_texts([text])
        return batch[0] if batch else None

__all__ = ["BGEEmbedding"]
