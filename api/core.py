import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

from embeddings.bge_embedding import BGEEmbedding
from langchain_chroma import Chroma
from FlagEmbedding import FlagReranker
from langchain_openai import ChatOpenAI
import torch

load_dotenv()
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# --- 数据库配置 (SQLite) ---
DB_URL = f"sqlite:///{PROJECT_ROOT}/data/knowledge_base.db"
Base = declarative_base()
engine = create_engine(DB_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class DocumentRecord(Base):
    __tablename__ = "documents"
    id = Column(String, primary_key=True)
    user_id = Column(String, default="admin", index=True)
    name = Column(String)
    path = Column(String)
    category = Column(String) # 'default' / 'user'
    upload_time = Column(DateTime, default=datetime.now)

Base.metadata.create_all(bind=engine)

# --- 模型单例加载 ---
print("⏳ 正在加载 RAG 核心模型组件...")
device = "cuda" if torch.cuda.is_available() else "cpu"

# 1. 嵌入模型
bge_model = BGEEmbedding(model_name="e:/rag-project/models/bge-m3")

# 2. 向量库
vector_store = Chroma(
    collection_name="test",
    embedding_function=bge_model._embeddings,
    persist_directory=str(PROJECT_ROOT / "data" / "chroma" / "test")
)

# 3. 重排模型
reranker = FlagReranker("e:/rag-project/models/bge-reranker-v2-m3", use_fp16=True)

# 4. LLM
llm = ChatOpenAI(
    model="deepseek-chat",
    temperature=0,
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
    streaming=True
)