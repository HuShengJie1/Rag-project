# scripts/init_system_docs.py
import sys
from pathlib import Path

# 路径配置
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "api"))

from api_manager import process_ingestion_task
from core import SessionLocal, DocumentRecord

SYSTEM_DOCS_DIR = PROJECT_ROOT / "data" / "system_docs"
SYSTEM_DOCS_DIR.mkdir(parents=True, exist_ok=True)

def ingest_system_files():
    """扫描 system_docs 目录并将文件作为 'system' 用户入库"""
    print(f"🚀 开始扫描制度文件目录: {SYSTEM_DOCS_DIR}")
    
    files = list(SYSTEM_DOCS_DIR.glob("*.*"))
    if not files:
        print("⚠️ 目录为空，请先放入 .pdf 或 .md 文件")
        return

    db = SessionLocal()
    for file_path in files:
        if file_path.suffix not in ['.pdf', '.md', '.txt']:
            continue
            
        # 1. 定义 ID 和 用户身份
        filename = file_path.name
        file_id = f"SYSTEM_{filename}"  #以此前缀区分，防止与用户文件重名
        user_id = "system"  # 👈 关键：特殊的身份标识

        print(f"处理中: {filename} ...")

        # 2. 写入 SQLite (如果不存在)
        existing = db.query(DocumentRecord).filter(DocumentRecord.id == file_id).first()
        if not existing:
            new_doc = DocumentRecord(
                id=file_id,
                user_id=user_id,
                name=filename,
                path=str(file_path),
                category="system" # 👈 分类标记
            )
            db.add(new_doc)
            db.commit()

        # 3. 调用 api_manager 中的逻辑进行向量化
        # 注意：这里复用了你之前写的逻辑，完全通用！
        process_ingestion_task(file_id, user_id, file_path, filename)

    db.close()
    print("✅ 制度文件入库完成！")

if __name__ == "__main__":
    ingest_system_files()