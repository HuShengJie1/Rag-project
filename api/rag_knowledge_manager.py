"""
项目名称：基于 DeepSeek + BGE-M3 的笔记本式 RAG 知识库系统
后端职责：文档元数据管理 (SQLAlchemy)、向量检索 (ChromaDB)、流式对话转发
"""

import os
import uuid
import shutil
import json
from pathlib import Path
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# 导入自定义嵌入模型和消息模型
from embeddings.bge_embedding import BGEEmbedding
from langchain_chroma import Chroma
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
import torch

# --- 1. 环境与路径配置 ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent
UPLOAD_DIR = PROJECT_ROOT / "data" / "uploads"
DB_DIR = PROJECT_ROOT / "data"
DB_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# --- 2. 文档元数据管理 (SQLAlchemy/SQLite) ---
# 负责记录左侧来源列表的信息
DB_URL = f"sqlite:///{DB_DIR}/knowledge_base.db"
Base = declarative_base()
engine = create_engine(DB_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class DocumentRecord(Base):
    """
    文档记录表：存储文件名、路径及分类
    用于前端左侧“来源”栏的展示与管理
    """
    __tablename__ = "documents"
    id = Column(String, primary_key=True, index=True)
    name = Column(String)
    path = Column(String)
    category = Column(String)  # 'system_default' 或 'user_upload'
    upload_time = Column(DateTime, default=datetime.now)

Base.metadata.create_all(bind=engine)

# --- 3. RAG 核心组件初始化 ---
print("⏳ 正在初始化 BGE-M3 嵌入模型与向量库...")
EMBED_PATH = "e:/rag-project/models/bge-m3"
bge_model = BGEEmbedding(model_name=EMBED_PATH)

# 初始化向量库，用于存储和检索课程计划表等数据
vector_store = Chroma(
    collection_name="bge_collection",
    embedding_function=bge_model._embeddings,
    persist_directory=str(PROJECT_ROOT / "data" / "chroma" / "bge_v2_db")
)

# 初始化 DeepSeek 模型
llm = ChatOpenAI(
    model="deepseek-chat",
    temperature=0,
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
    streaming=True
)

# --- 4. API 服务配置 ---
app = FastAPI(title="Notebook RAG Backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    prompt: str
    top_k: int = 4
    # 预留给 NotebookLM 的功能：指定文件 ID 列表进行检索
    source_filter: Optional[List[str]] = None 

# --- 5. 业务逻辑接口 ---

@app.get("/api/sources")
def list_sources():
    """获取左侧所有来源文档列表"""
    db = SessionLocal()
    docs = db.query(DocumentRecord).all()
    db.close()
    return [{"id": d.id, "name": d.name, "category": d.category} for d in docs]

@app.post("/api/upload")
async def upload_document(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """处理用户上传文档并触发后台异步入库"""
    file_id = str(uuid.uuid4())
    save_path = UPLOAD_DIR / f"{file_id}_{file.filename}"
    
    with save_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # 保存元数据到 SQLite
    db = SessionLocal()
    new_doc = DocumentRecord(id=file_id, name=file.filename, path=str(save_path), category="user_upload")
    db.add(new_doc)
    db.commit()
    db.close()
    
    # TODO: 启动后台异步处理 (解析 -> 分块 -> 入库)
    # background_tasks.add_task(process_ingestion, file_id, save_path)
    
    return {"id": file_id, "name": file.filename, "status": "processing"}

# --- 后续：此处将添加具体的 Chat 逻辑 (Part 2) ---

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)