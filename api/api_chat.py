import json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict
# 👇 新增导入 AIMessage 用于处理助手历史消息
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from core import vector_store, reranker, llm

router = APIRouter(prefix="/api")

class ChatRequest(BaseModel):
    prompt: str
    top_k: int = 5
    source_filter: Optional[List[str]] = None
    # 👇 接收前端传来的历史记录 [{"role": "user", "content": "..."}, ...]
    history: List[Dict[str, str]] = []

@router.post("/chat")
async def chat_with_rag(request: ChatRequest):
    current_user = "admin"
    
    # --- 1. 构造更严谨的过滤条件 (修复逻辑漏洞) ---
    # 基础权限：只能看 admin 的或者 system 的
    permission_filter = {
        "$or": [
            {"user_id": {"$eq": current_user}},
            {"user_id": {"$eq": "system"}}
        ]
    }

    if not request.source_filter:
        # 情况 A: 用户没勾选，在所有权限范围内搜
        filter_conditions = permission_filter
    else:
        # 情况 B: 用户勾选了特定文件
        # 逻辑：(文件ID 在勾选列表中) AND (拥有权限)
        filter_conditions = {
            "$and": [
                {"file_id": {"$in": request.source_filter}},
                permission_filter
            ]
        }

    # --- 2. 粗排 ---
    # 注意：如果 source_filter 列表为空但字段存在，可能会导致 filter 报错，前端需确保传 null 或非空列表
    initial_docs = vector_store.similarity_search(
        request.prompt, 
        k=30, 
        filter=filter_conditions
    )
    
    # --- 3. 重排 (Rerank) ---
    # 如果粗排没拿到数据，直接跳过重排防止报错
    if not initial_docs:
        final_docs = []
    else:
        rerank_pairs = [[request.prompt, doc.page_content] for doc in initial_docs]
        scores = reranker.compute_score(rerank_pairs)
        
        # 兼容处理：有些 reranker 返回的是 float，有些是 list
        if isinstance(scores, float): scores = [scores]
        
        for i, doc in enumerate(initial_docs):
            doc.metadata["rerank_score"] = float(scores[i])
        
        final_docs = sorted(initial_docs, key=lambda x: x.metadata["rerank_score"], reverse=True)[:request.top_k]

    # --- 4. 构造证据包 ---
    evidence_list = [{
        "source": d.metadata.get("source", "未知来源"),
        "pages": d.metadata.get("page_labels", "?"),
        "content": d.page_content,
        "score": round(d.metadata.get("rerank_score", 0), 4)
    } for d in final_docs]

    # --- 5. 构造历史消息链 (核心记忆功能) ---
    messages = []
    
    # A. 系统提示词
    system_prompt = """你是一个专业的知识库助手。请基于提供的【参考资料】回答用户问题。
    1. 如果资料中有答案，请详细回答。
    2. 如果资料中没有提到，请根据上下文推断，或者诚实地回答“资料中未提及”。
    3. 请结合用户的历史提问进行连贯的对话。
    """
    messages.append(SystemMessage(content=system_prompt))

    # B. 注入历史记录 (保留最近 6 轮，防止 Token 溢出)
    # 过滤掉空的或无效的历史
    clean_history = request.history[-6:] 
    for msg in clean_history:
        if msg['role'] == 'user':
            messages.append(HumanMessage(content=msg['content']))
        elif msg['role'] == 'assistant':
            # 过滤掉之前回复中的 "正在思考..." 等前端占位符（虽然前端过滤过了，后端再保险一次）
            if msg['content']: 
                messages.append(AIMessage(content=msg['content']))

    # C. 注入当前 RAG 上下文和问题
    context_text = "\n\n".join([
        f"--- 来源: {d.metadata.get('source')} (P{d.metadata.get('page_labels')}) ---\n{d.page_content}" 
        for d in final_docs
    ])
    
    # 将“参考资料”和“当前问题”组合成最新的 User Message
    final_user_content = f"【参考资料】:\n{context_text}\n\n【用户当前问题】:\n{request.prompt}"
    messages.append(HumanMessage(content=final_user_content))

    # --- 6. 流式生成 ---
    async def stream_generator():
        # 先发证据包
        yield json.dumps({"evidence": evidence_list}, ensure_ascii=False) + "---METADATA_SEPARATOR---"
        
        # 再发 AI 思考内容
        # 注意：这里传入的是构建好的 messages 列表（包含历史）
        async for chunk in llm.astream(messages):
            if chunk.content: 
                yield chunk.content

    return StreamingResponse(stream_generator(), media_type="text/event-stream")