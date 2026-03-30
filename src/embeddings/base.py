
"""
src/embeddings/base.py
定义通用的 LangChain 适配器，实现一次编写，到处运行。
"""
from typing import List, Optional, Sequence

# 建议让适配器继承 LangChain 原生的 Embeddings 接口，这样 IDE 提示更友好
try:
    from langchain_core.embeddings import Embeddings
except ImportError:
    # 兼容旧版本
    class Embeddings: pass

class LangChainEmbedderAdapter(Embeddings):
    """
    通用适配器：将自定义 Embedding 模型包装为 LangChain 标准接口。
    只要模型类拥有 embed_text 和 embed_texts 方法即可使用。
    """
    def __init__(self, embedder: any) -> None:
        self.embedder = embedder

    def embed_query(self, text: str) -> List[float]:
        """适配单条查询：调用原始类的 embed_text"""
        return self.embedder.embed_text(text) or []

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """适配批量文档：调用原始类的 embed_texts"""
        # 过滤 None 值，确保 Chroma 不报错
        results = self.embedder.embed_texts(texts)
        return [vec for vec in results if vec is not None]