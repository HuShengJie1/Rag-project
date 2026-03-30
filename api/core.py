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
MODELS_ROOT = Path(os.getenv("LOCAL_MODELS_ROOT", str(PROJECT_ROOT / "models"))).expanduser()


def _resolve_model_path(*candidates: Path) -> str:
    for p in candidates:
        if str(p).strip() and str(p) not in (".", "") and p.exists():
            return str(p)
    # 保底返回首个候选，便于错误信息可读
    return str(candidates[0])


def _optional_env_path(env_key: str) -> Path | None:
    value = (os.getenv(env_key) or "").strip()
    if not value:
        return None
    return Path(value).expanduser()

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

bge_candidates = [MODELS_ROOT / "bge-m3", MODELS_ROOT / "hf_cache" / "hub" / "BAAI" / "bge-m3"]
reranker_candidates = [
    MODELS_ROOT / "bge-reranker-v2-m3",
    MODELS_ROOT / "hf_cache" / "hub" / "BAAI" / "bge-reranker-v2-m3",
]

env_bge = _optional_env_path("BGE_M3_PATH")
env_rerank = _optional_env_path("BGE_RERANKER_PATH")
if env_bge is not None:
    bge_candidates.insert(0, env_bge)
if env_rerank is not None:
    reranker_candidates.insert(0, env_rerank)

bge_model_path = _resolve_model_path(*bge_candidates)
reranker_model_path = _resolve_model_path(*reranker_candidates)

# 1. 嵌入模型
bge_model = BGEEmbedding(model_name=bge_model_path)

# 2. 向量库
vector_store = Chroma(
    collection_name="test",
    embedding_function=bge_model._embeddings,
    persist_directory=str(PROJECT_ROOT / "data" / "chroma" / "test")
)

# 3. 重排模型
reranker = FlagReranker(reranker_model_path, use_fp16=True)

# 4. LLM
llm = ChatOpenAI(
    model=os.getenv("KIMI_MODEL", "moonshot-v1-128k"),
    temperature=0,
    api_key=os.getenv("KIMI_API_KEY"),
    base_url=os.getenv("KIMI_BASE_URL", "https://api.moonshot.cn/v1"),
    streaming=True
)
