import os
import json
import asyncio
from pathlib import Path
from typing import List
from fastapi import FastAPI, HTTPException, Body
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# 导入自定义模块
import sys
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from embeddings.base import LangChainEmbedderAdapter
from embeddings.QZhou_Zh_embedding import QZhouEmbedding
from embeddings.bge_embedding import BGEEmbedding
from langchain_chroma import Chroma
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from FlagEmbedding import FlagReranker  # 👈 新增：重排模型库

load_dotenv()

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 路径配置 ---
MODELS_ROOT = Path(os.getenv("LOCAL_MODELS_ROOT", str(PROJECT_ROOT / "models"))).expanduser()


def _resolve_model_path(*candidates: Path) -> str:
    for p in candidates:
        if p.exists():
            return str(p)
    return str(candidates[0])


def _optional_env_path(env_key: str) -> Path | None:
    value = (os.getenv(env_key) or "").strip()
    if not value:
        return None
    return Path(value).expanduser()


embed_candidates = [MODELS_ROOT / "bge-m3", MODELS_ROOT / "hf_cache" / "hub" / "BAAI" / "bge-m3"]
rerank_candidates = [
    MODELS_ROOT / "bge-reranker-v2-m3",
    MODELS_ROOT / "hf_cache" / "hub" / "BAAI" / "bge-reranker-v2-m3",
]

env_bge = _optional_env_path("BGE_M3_PATH")
env_rerank = _optional_env_path("BGE_RERANKER_PATH")
if env_bge is not None:
    embed_candidates.insert(0, env_bge)
if env_rerank is not None:
    rerank_candidates.insert(0, env_rerank)

EMBED_PATH = _resolve_model_path(*embed_candidates)
RERANK_PATH = _resolve_model_path(*rerank_candidates)  # 👈 重排模型路径
PERSIST_DIR = PROJECT_ROOT / "data" / "chroma" / "bge_v2_db"

# --- 1. 加载嵌入模型 ---
print("⏳ 正在加载 QZhou-7B 嵌入模型...")
raw_embedder = BGEEmbedding(model_name=EMBED_PATH)
adapter = LangChainEmbedderAdapter(raw_embedder)
vector_store = Chroma(
    collection_name="bge_collection",
    embedding_function=adapter,
    persist_directory=str(PERSIST_DIR)
)

# --- 2. 加载重排模型 (针对 4070 优化) ---
print("⏳ 正在加载 BGE-Reranker-v2-m3 重排模型...")
reranker = FlagReranker(RERANK_PATH, use_fp16=True) # 4070 使用半精度，速度极快

# --- 3. 加载 LLM ---
llm = ChatOpenAI(
    model=os.getenv("KIMI_MODEL", "moonshot-v1-128k"),
    temperature=0.2,
    api_key=os.getenv("KIMI_API_KEY"),
    base_url=os.getenv("KIMI_BASE_URL", "https://api.moonshot.cn/v1"),
    streaming=True
)

class ChatRequest(BaseModel):
    prompt: str
    top_k: int = 5

@app.post("/api/chat")
async def chat_with_rag(request: ChatRequest):
    try:
        # --- 步骤 A: 粗排 (向量检索) ---
        # 我们取 15 个候选，确保那个“乱码表格”分块能被抓到
        initial_docs = vector_store.similarity_search(request.prompt, k=30)
        
        if not initial_docs:
            return StreamingResponse(iter(["未找到相关参考材料。"]), media_type="text/plain")

        # --- 步骤 B: 精排 (Rerank) ---
        # 构造重排输入对 [问题, 文档正文]
        rerank_pairs = [[request.prompt, doc.page_content] for doc in initial_docs]
        scores = reranker.compute_score(rerank_pairs)
        
        # 将分数存入文档并重新排序
        for i, doc in enumerate(initial_docs):
            doc.metadata["rerank_score"] = float(scores[i])
        
        # 按分数从高到低排序，取用户要求的 top_k
        final_docs = sorted(initial_docs, key=lambda x: x.metadata["rerank_score"], reverse=True)[:request.top_k]

        # --- 步骤 C: 构造上下文 ---
        evidence_list = []
        context_text = ""
        for i, doc in enumerate(final_docs):
            meta = doc.metadata or {}
            score = meta.get("rerank_score", 0)
            
            ev = {
                "source": meta.get("source", "未知文档"),
                "pages": meta.get("page_labels", "N/A"),
                "content": doc.page_content,
                "score": round(score, 4) # 传回分数方便调试
            }
            evidence_list.append(ev)
            # 在上下文中加入证据编号，方便模型定位
            context_text += f"\n【材料 #{i+1}】(相关度: {round(score,2)})\n{doc.page_content}\n"

        # --- 步骤 D: 生成流式回答 ---
        async def stream_generator():
            # 首先发送元数据
            meta_payload = {"evidence": evidence_list}
            yield json.dumps(meta_payload, ensure_ascii=False) + "---METADATA_SEPARATOR---"

            # 优化后的 System Prompt：更有“勇气”处理乱码表格
            system_prompt = (
                "你是一个极其严谨且智能的工程教育认证专家。\n"
                "你的任务是根据提供的多段参考材料回答用户问题。请遵循以下原则：\n"
                "1. 忽略材料中由于 OCR 解析产生的杂质（如‘子刀’、‘深以’、‘一角任’、‘子门’等），尝试通过上下文理解表格内容。\n"
                "2. 优先寻找与问题直接匹配的表格数据。即使材料分散，也要进行跨段落整合。\n"
                "3. 回答必须基于材料。如果所有材料确实都没有提及，请礼貌告知。\n"
                "4. 如果材料中存在课程列表、学分、指标点等信息，请以清晰的 Markdown 格式输出。"
            )
            
            user_prompt = f"请根据以下参考材料回答问题：\n{context_text}\n\n问题：{request.prompt}"
            
            async for chunk in llm.astream([
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]):
                if chunk.content:
                    yield chunk.content

        return StreamingResponse(stream_generator(), media_type="text/event-stream")

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    # 4070 建议开启单个 worker 以保证显存稳定
    uvicorn.run(app, host="0.0.0.0", port=8000, workers=1)
