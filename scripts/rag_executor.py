"""
最小 RAG 执行脚本：实现基于 QZhou 高维向量的精准检索与 DeepSeek 生成。
"""

from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from langchain_chroma import Chroma
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

# 路径对齐
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from embeddings.QZhou_Zh_embedding import QZhouEmbedding 

# 默认配置
PERSIST_DIR = PROJECT_ROOT / "data" / "chroma" / "qzhou_7b_db"
COLLECTION_NAME = "qzhou_7b_chunks"
DEFAULT_NO_EVIDENCE = "未在材料中找到依据"

class _LCEmbeddingAdapter:
    """将 QZhouEmbedding 适配为 LangChain 接口。"""
    def __init__(self, embedder: QZhouEmbedding) -> None:
        self.embedder = embedder
    
    def embed_query(self, text: str) -> List[float]:
        return self.embedder.embed_text(text) or []

    def embed_documents(self, texts: Sequence[str]) -> List[List[float]]:
        return [vec for vec in self.embedder.embed_texts(texts) if vec is not None]

def retrieve_chunks(vector_store: Chroma, query: str, top_k: int) -> Tuple[List[str], str]:
    """执行检索并返回证据 ID 与上下文。"""
    # 使用 similarity_search 即可，如果需要分数可用 similarity_search_with_score
    results = vector_store.similarity_search(query, k=top_k)
    
    evidence = []
    contexts = []
    for doc in results:
        meta = doc.metadata or {}
        # 提取我们在入库阶段保存的 chunk_id 和页码
        cid = meta.get("chunk_id")
        page = meta.get("page_labels")
        source = meta.get("source")
        
        evidence.append(f"{cid} (Page: {page})")
        contexts.append(f"文件[{source}] 第{page}页内容：\n{doc.page_content}")
    
    return evidence, "\n\n".join(contexts)

def get_llm(provider: str, model: str) -> ChatOpenAI:
    """获取 LLM 实例，修正了 API Key 和 Temperature。"""
    if provider == "deepseek":
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError("❌ 错误：环境变量 DEEPSEEK_API_KEY 未设置！")
            
        return ChatOpenAI(
            model=model,
            temperature=0.1,  # 修正：工程认证问答建议低随机性
            api_key=api_key,
            base_url="https://api.deepseek.com",
        )
    # 可根据需要添加 openai 支持
    raise ValueError(f"暂不支持的提供商: {provider}")

def main() -> None:
    parser = argparse.ArgumentParser(description="工程认证 RAG 问答测试。")
    parser.add_argument("--query", type=str, default="毕业学分要求")
    parser.add_argument("--top-k", type=int, default=3)
    args = parser.parse_args()

    print(f"🧐 正在检索问题: {args.query} ...")

    try:
        # 1. 初始化模型与向量库
        embedder = QZhouEmbedding() 
        adapter = _LCEmbeddingAdapter(embedder)
        vector_store = Chroma(
            collection_name=COLLECTION_NAME,
            embedding_function=adapter,
            persist_directory=str(PERSIST_DIR),
        )

        # 2. 检索
        evidence_list, context_text = retrieve_chunks(vector_store, args.query, args.top_k)

        if not context_text.strip():
            print(f"Result: {DEFAULT_NO_EVIDENCE}")
            return

        # 3. 生成回答
        llm = get_llm("deepseek", "deepseek-chat")
        
        system_prompt = (
            "你是一个专业的工程教育认证助手。"
            "请严格基于提供的材料回答问题。如果材料中没有提及，请直白告知。保持客观、准确。"
        )
        user_prompt = f"【参考材料】：\n{context_text}\n\n【用户问题】：{args.query}"
        
        print("🤖 正在请求 DeepSeek 生成回答...")
        response = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)])
        
        # 4. 展示结果
        print("\n" + "="*50)
        print(f"📝 回答：\n{response.content}")
        print("-" * 50)
        print(f"🔗 证据链：{evidence_list}")
        print("="*50)

    except Exception as e:
        print(f"❌ 运行出错: {e}")

if __name__ == "__main__":
    main()