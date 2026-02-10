from fastapi import APIRouter, UploadFile, File, BackgroundTasks
from core import SessionLocal, DocumentRecord, vector_store, PROJECT_ROOT
import uuid, shutil, os
from pathlib import Path
from core import vector_store
router = APIRouter(prefix="/api")



@router.get("/sources")
async def list_sources():
    db = SessionLocal()
    docs = db.query(DocumentRecord).all()
    db.close()
    return [{"id": d.id, "name": d.name, "category": d.category} for d in docs]

@router.post("/upload")
async def upload_file(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    file_id = str(uuid.uuid4())
    current_user = "admin"
    save_path = PROJECT_ROOT / "data/uploads" / f"{file_id}_{file.filename}"
    save_path.parent.mkdir(parents=True, exist_ok=True)
    
    with save_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    db = SessionLocal()
    new_doc = DocumentRecord(id=file_id, name=file.filename, path=str(save_path), category="user")
    db.add(new_doc)
    db.commit()
    db.close()

    # 此处预留异步入库任务
    background_tasks.add_task(process_ingestion, file_id, save_path)
    return {"id": file_id, "name": file.filename, "status": "processing"}


def process_ingestion(file_id: str, user_id: str, file_path: Path, filename: str):
    """
    后台异步任务：执行 解析 -> 分块 -> 向量化入库
    """
    try:
        # 1. 读取文件内容 (建议之后对接 Marker 或 PyMuPDF)
        # 这里以读取文本文件为例
        raw_text = file_path.read_text(encoding="utf-8")

        # 2. 语义分块
        # 此时会生成类似于 [{'text': '...', 'metadata': {...}}, ...] 的列表
        from chunkers.chunking import chunk_markdown_content
        chunks = chunk_markdown_content(raw_text, source_name=filename)

        texts = []
        metadatas = []

        for c in chunks:
            texts.append(c['text'])
            
            # --- 第 3 项修改的核心：注入隔离标签 ---
            m = c['metadata']
            m["file_id"] = file_id    # 关联具体文件 ID
            m["user_id"] = user_id    # 关联具体用户 ID (方案 B 的核心)
            # --------------------------------------
            
            metadatas.append(m)

        # 3. 写入 ChromaDB 向量库
        # BGE-M3 模型会自动处理向量化过程
        vector_store.add_texts(
            texts=texts, 
            metadatas=metadatas
        )
        
        print(f"✅ [入库完成] 文件: {filename}, 用户: {user_id}, 分块数: {len(texts)}")

    except Exception as e:
        print(f"❌ [入库失败] {filename}: {str(e)}")