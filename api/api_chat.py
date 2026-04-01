import json
import re
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from core import vector_store, reranker, llm, SessionLocal, DocumentRecord
from pathlib import Path

router = APIRouter(prefix="/api")
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PARSED_MD_DIR = PROJECT_ROOT / "data" / "parsed" / "md"
UPLOAD_DIR = PROJECT_ROOT / "data" / "uploads"
SYSTEM_DOCS_DIR = PROJECT_ROOT / "data" / "system_docs"

def extract_complete_markdown(
    source_file: str,
    file_id: Optional[str] = None,
    full_md_path: Optional[str] = None,
) -> str:
    try:
        # 0) 优先使用 metadata 中直接给出的完整 markdown 路径
        if full_md_path:
            p = Path(full_md_path).expanduser()
            if p.exists() and p.is_file():
                return p.read_text(encoding="utf-8")

        # 1) 由 source 反推 parsed/md 里的完整 markdown（适配 .temp.md / .pdf / .docx / .md）
        clean_name = Path(str(source_file or "")).name.replace(".temp", "")
        base_md_name = Path(clean_name).with_suffix(".md").name
        parsed_candidate = PARSED_MD_DIR / base_md_name
        if parsed_candidate.exists():
            return parsed_candidate.read_text(encoding="utf-8")

        # 2) 通过 file_id 回查原始文件路径，优先读取原生 md/txt，或再映射 parsed/md
        if file_id:
            db = SessionLocal()
            try:
                doc = db.query(DocumentRecord).filter(DocumentRecord.id == file_id).first()
                if doc and doc.path:
                    original_path = Path(doc.path)
                    if original_path.exists() and original_path.suffix.lower() in {".md", ".txt"}:
                        return original_path.read_text(encoding="utf-8")

                    mapped_md = PARSED_MD_DIR / f"{original_path.stem}.md"
                    if mapped_md.exists():
                        return mapped_md.read_text(encoding="utf-8")
            finally:
                db.close()

        # 3) 最后兜底：在 uploads/system_docs 内按同名 md 查找
        fallback_candidates = [
            UPLOAD_DIR / base_md_name,
            SYSTEM_DOCS_DIR / base_md_name,
        ]
        for p in fallback_candidates:
            if p.exists() and p.is_file():
                return p.read_text(encoding="utf-8")

        return ""
    except Exception as e:
        print(f"❌ [寻址定位] 读取文件时发生错误: {e}")
        return ""

class ChatRequest(BaseModel):
    prompt: str
    top_k: int = 5
    source_filter: Optional[List[str]] = None
    history: List[Dict[str, str]] = []

@router.post("/chat")
async def chat_with_rag(request: ChatRequest):
    current_user = "admin"
    
    # --- 1. 构造更严谨的过滤条件 ---
    permission_filter = {
        "$or": [
            {"user_id": {"$eq": current_user}},
            {"user_id": {"$eq": "system"}}
        ]
    }

    if not request.source_filter:
        filter_conditions = permission_filter
    else:
        filter_conditions = {
            "$and": [
                {"file_id": {"$in": request.source_filter}},
                permission_filter
            ]
        }

    # --- 2. 粗排 ---
    initial_docs = vector_store.similarity_search(
        request.prompt, 
        k=30, 
        filter=filter_conditions
    )
    
    # --- 3. 重排 (Rerank) ---
    if not initial_docs:
        final_docs = []
    else:
        rerank_pairs = [[request.prompt, doc.page_content] for doc in initial_docs]
        scores = reranker.compute_score(rerank_pairs)
        
        if isinstance(scores, float): scores = [scores]
        
        for i, doc in enumerate(initial_docs):
            doc.metadata["rerank_score"] = float(scores[i])
        
        final_docs = sorted(initial_docs, key=lambda x: x.metadata["rerank_score"], reverse=True)[:request.top_k]

    # 🟢 修改点 1：构造证据包时，强行加入从 1 开始的 index 序号
    # 这个 evidence_list 将会传给前端，前端依据 index 来判断用户点击了哪个标号
    evidence_list = []
    
    # 为了避免同一个完整文档被重复读取多次（因为可能匹配到同一个文件的多个切片），
    # 我们可以加一个小缓存，提升一点性能。
    md_cache = {} 
    
    for idx, d in enumerate(final_docs):
        source_name = d.metadata.get("source", "未知来源")
        page_label = str(d.metadata.get("page_labels", "1"))
        file_id = d.metadata.get("file_id")
        full_md_path = d.metadata.get("full_md_path")
        
        # 如果缓存里没有这个文件，就去读一次
        cache_key = f"{file_id}|{source_name}|{full_md_path}"
        if cache_key not in md_cache:
            md_cache[cache_key] = extract_complete_markdown(
                source_name,
                file_id=file_id,
                full_md_path=full_md_path,
            )
            
        full_document_text = md_cache[cache_key]
        
        evidence_list.append({
            "index": idx + 1,
            "source": source_name,
            "pages": page_label,
            "content": d.page_content, # 原始切片内容，前端用来做精确匹配和高亮
            "full_content": full_document_text or d.page_content, # 如果找到了完整文档就用完整文档，没找到就用切片兜底
            "score": round(d.metadata.get("rerank_score", 0), 4)
        })

    messages = []
    
    # 🟢 修改点 2：重写 System Prompt，加入强硬的引文规则
    system_prompt = """你是一个专业的知识库助手。请基于提供的【参考资料】回答用户问题。
要求：
1. 必须且只能使用提供的参考资料回答。如果资料中没有提到，请根据上下文推断，或者诚实地回答“资料中未提及”，绝对不能捏造。
2. 请结合用户的历史提问进行连贯的对话。
3. ⚠️ 重要规定：在回答的每一句话或每一个关键结论末尾，必须严格标注信息来源的编号！格式必须为如 [1] 或 [1][2]。如果没有提供参考资料，则无需标注。
"""
    messages.append(SystemMessage(content=system_prompt))

    # B. 注入历史记录
    clean_history = request.history[-6:] 
    for msg in clean_history:
        if msg['role'] == 'user':
            messages.append(HumanMessage(content=msg['content']))
        elif msg['role'] == 'assistant':
            if msg['content']: 
                messages.append(AIMessage(content=msg['content']))

    # 🟢 修改点 3：组装传给大模型的 Context 时，把 [1], [2] 标号拼接到段落开头
    # 这样大模型在阅读上下文时，才知道每一段对应的“编号”是什么
    context_text = "\n\n".join([
        # 注意这里使用了 d["index"] 对应的编号
        f"[{d['index']}] 来源: {d['source']} (P{d['pages']})\n内容: {d['content']}" 
        for d in evidence_list # 👈 遍历 evidence_list 而不是 final_docs，保证编号一致性
    ])
    
    final_user_content = f"【参考资料】:\n{context_text}\n\n【用户当前问题】:\n{request.prompt}"
    messages.append(HumanMessage(content=final_user_content))

    # --- 6. 流式生成 ---
    async def stream_generator():
        # 🟢 修改点 4（无实质改动，仅提醒）：
        # 这里你原有的代码就非常棒！前端只需要按照 "---METADATA_SEPARATOR---" 来切分，
        # 就能拿到包含 index 的 evidence_list 字典了。
        yield json.dumps({"evidence": evidence_list}, ensure_ascii=False) + "---METADATA_SEPARATOR---"
        
        async for chunk in llm.astream(messages):
            if chunk.content: 
                yield chunk.content

    return StreamingResponse(stream_generator(), media_type="text/event-stream")
