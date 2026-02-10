"""基于 LangChain 的 QZhou-Embedding-Zh 文本向量化封装。"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple
import torch # 增加 torch 检查显存
from langchain_huggingface.embeddings import HuggingFaceEmbeddings as _HuggingFaceEmbeddings

class QZhouEmbedding:
    """
    使用 HuggingFaceEmbeddings 加载金山云 QZhou-Embedding-Zh 模型。
    该模型基于 Qwen2-7B，在中文工程认证文档检索中具有极高的语义召回率。
    """

    _MODEL_CACHE: Dict[Tuple[str, Optional[str]], _HuggingFaceEmbeddings] = {}

    def __init__(
        self,
        # 修改为截图中的模型路径
        model_name: str = "e:/rag-project/models/QZhou-Embedding-Zh", 
        device: Optional[str] = None,
        batch_size: int = 8,  # ⚠️ 注意：7B 模型显存占用高，建议调小 batch_size
        normalize_embeddings: bool = True,
    ) -> None:
        """
        初始化 QZhou 向量模型。
        """
        # 自动检测设备，优先使用 CUDA
        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
            
        cache_key = (model_name, device)
        if cache_key not in self._MODEL_CACHE:
            # 对于 Qwen2 架构的模型，建议显式指定信任远程代码（如有需要）
            model_kwargs = {
                "device": device,
                "trust_remote_code": False,
                # 如果显存不足，可以尝试使用半精度加载
                "model_kwargs": {"torch_dtype": torch.float16 if device == "cuda" else torch.float32}
            }
            encode_kwargs = {
                "batch_size": batch_size, 
                "normalize_embeddings": normalize_embeddings
            }
            
            print(f"🚀 正在加载 {model_name} 到 {device}...")
            self._MODEL_CACHE[cache_key] = _HuggingFaceEmbeddings(
                model_name=model_name,
                model_kwargs=model_kwargs,
                encode_kwargs=encode_kwargs,
            )
            
        self._embeddings = self._MODEL_CACHE[cache_key]

    def _filter_texts(self, texts: Sequence[Optional[str]]) -> Tuple[List[str], List[int]]:
        """过滤空字符串或 None，确保向量化过程不因噪声中断。"""
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

        # 直接调用底层的 embed_documents
        embeddings = self._embeddings.embed_documents(valid_texts)
        
        for emb, idx in zip(embeddings, indices):
            results[idx] = list(emb)
        return results

    def embed_text(self, text: Optional[str]) -> Optional[List[float]]:
        """单条文本向量化。"""
        batch = self.embed_texts([text])
        return batch[0] if batch else None

__all__ = ["QZhouEmbedding"]