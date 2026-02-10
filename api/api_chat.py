import json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
from langchain_core.messages import HumanMessage, SystemMessage
from core import vector_store, reranker, llm

router = APIRouter(prefix="/api")

class ChatRequest(BaseModel):
    prompt: str
    top_k: int = 5
    source_filter: Optional[List[str]] = None # 👈 NotebookLM 勾选功能

@router.post("/chat")
async def chat_with_rag(request: ChatRequest):
    current_user = "admin"
    
    filter_conditions = {"user_id":current_user}
    # 1. 构造过滤条件
    search_kwargs = {"k": 30}
    if request.source_filter:
        search_kwargs["filter"] = {"file_id": {"$in": request.source_filter}}

    # 2. 粗排
    initial_docs = vector_store.similarity_search(request.prompt, **search_kwargs)
    
    # 3. 重排 (Rerank)
    rerank_pairs = [[request.prompt, doc.page_content] for doc in initial_docs]
    scores = reranker.compute_score(rerank_pairs)
    for i, doc in enumerate(initial_docs):
        doc.metadata["rerank_score"] = float(scores[i])
    
    final_docs = sorted(initial_docs, key=lambda x: x.metadata["rerank_score"], reverse=True)[:request.top_k]

    # 4. 构造证据与流式生成
    evidence_list = [{
        "source": d.metadata.get("source"),
        "pages": d.metadata.get("page_labels"),
        "content": d.page_content,
        "score": round(d.metadata.get("rerank_score"), 4)
    } for d in final_docs]

    async def stream_generator():
        yield json.dumps({"evidence": evidence_list}, ensure_ascii=False) + "---METADATA_SEPARATOR---"
        
        system_prompt = "你是一个工程教育认证专家。请忽略 OCR 噪音，基于材料回答..."
        context_text = "\n".join([f"【材料 #{i+1}】\n{d.page_content}" for i, d in enumerate(final_docs)])
        
        async for chunk in llm.astream([
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"参考：\n{context_text}\n\n问题：{request.prompt}")
        ]):
            if chunk.content: yield chunk.content

    return StreamingResponse(stream_generator(), media_type="text/event-stream")