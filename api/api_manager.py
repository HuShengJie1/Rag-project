import os
import uuid
import shutil
import sys
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
import urllib.parse
# 确保能引用到 src 目录下的模块
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

# 从项目组件中导入
from core import SessionLocal, DocumentRecord, vector_store  #
from chunkers.chunking import chunk_markdown_file           #
from loaders.mineru_loader import load_pdf, load_docx

router = APIRouter(prefix="/api")
UPLOAD_DIR = PROJECT_ROOT / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# --- 1. 后台异步入库逻辑 ---

def _normalize_metadata(value: object):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return ", ".join(str(i) for i in value)
    return str(value)

def get_unique_path(directory: Path, filename: str) -> Path:
    """
    检测文件名是否冲突，如果冲突则生成 (1), (2) 风格的新路径。
    例如: data.pdf -> data(1).pdf
    """
    file_path = directory / filename
    
    # 如果文件不存在，直接返回原路径
    if not file_path.exists():
        return file_path

    # 如果存在，开始循环尝试 (1), (2)...
    stem = Path(filename).stem   # 文件名不带后缀 (如: data)
    suffix = Path(filename).suffix # 后缀 (如: .pdf)
    counter = 1

    while True:
        new_filename = f"{stem}({counter}){suffix}"
        new_path = directory / new_filename
        if not new_path.exists():
            return new_path
        counter += 1

def process_ingestion_task(file_id: str, user_id: str, file_path: Path, filename: str):
    """
    异步任务：类型判断 -> 解析 -> 转存临时MD -> 分块 -> 注入元数据 -> 写入 ChromaDB
    """
    temp_md_path = None # 初始化临时路径变量
    
    try:
        print(f"⏳ [后台任务] 开始处理文件: {filename}")
        
        # --- 步骤 A: 根据后缀判断解析方式 ---
        suffix = file_path.suffix.lower()
        raw_records = []

        if suffix == ".pdf":
            # PDF: 使用 MinerU 本地模型解析为 Markdown
            print("   ↳ 检测到 PDF，正在使用 MinerU 解析...")
            raw_records = load_pdf(str(file_path))

        elif suffix == ".docx":
            # DOCX: 使用 MinerU office 模块解析
            print("   ↳ 检测到 DOCX，正在使用 MinerU 解析...")
            raw_records = load_docx(str(file_path))
        
        elif suffix in [".md", ".txt"]:
            # 文本: 直接读取
            print("   ↳ 检测到 Markdown/Text，直接读取...")
            raw_text = file_path.read_text(encoding="utf-8")
            raw_records = [{
                "doc_name": file_path.name,
                "page": 1,
                "text": raw_text,
                "section_path": None,
            }]
        
        else:
            print(f"⚠️ 跳过不支持的文件格式: {suffix}")
            return

        # --- 步骤 B: 创建临时文件以适配 chunk_markdown_file ---
        # 你的 chunking.py 是通过 path.read_text() 读取的，所以我们需要把解析好的内容
        # (比如 PDF 转出来的文字) 存回一个临时的 .md 文件里给它读。
        
        # 创建一个同名但后缀为 .temp.md 的临时文件
        temp_md_path = file_path.with_suffix(".temp.md")
        content = "\n\n\n".join([str(rec.get("text", "")) for rec in raw_records])
        temp_md_path.write_text(content, encoding="utf-8")
        
        # --- 步骤 C: 语义分块并注入隔离标签 (file_id & user_id) ---
        # 注意：这里传入的是 temp_md_path
        chunks = chunk_markdown_file(
            path=temp_md_path,
            file_id=file_id,
            user_id=user_id
        )

        if not chunks:
            print(f"⚠️ 文件 {filename} 未产生有效分块")
            return

        # --- 步骤 D: 准备写入向量库的数据 ---
        texts = [c["text"] for c in chunks]
        
        # 修正 metadata 中的 source 字段
        # 因为我们用了临时文件，source 可能会变成 "xxx.temp.md"
        # 我们这里手动把它改回原始文件名，保持数据显示好看
        metadatas = []
        for c in chunks:
            extra = c.get("metadata",{})
            meta = {
                "chunk_id" : c.get("chunk_id"),
                "user_id" : extra.get("user_id"),
                "file_id" : extra.get("file_id"),
                "source" : extra.get("source"),
                "page_labels" : extra.get("page_labels"),
                "headers" : extra.get("headers"),
                "chunk_seq" : extra.get("chunk_seq")
            }
            metadatas.append({k: _normalize_metadata(v) for k, v in meta.items()})

        # --- 步骤 E: 增量写入 ChromaDB ---
        vector_store.add_texts(texts=texts, metadatas=metadatas)
        
        print(f"✅ [入库成功] 来源: {filename}, 用户: {user_id}, 块数: {len(texts)}")
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"❌ [入库失败] {filename}: {str(e)}")
        
    finally:
        # --- 步骤 F: 清理临时文件 ---
        # 无论成功还是失败，都要把生成的 .temp.md 删掉，保持文件夹整洁
        if temp_md_path and temp_md_path.exists():
            try:
                os.remove(temp_md_path)
                print("   ↳ 临时文件已清理")
            except Exception:
                pass
# --- 2. 来源管理接口 ---

@router.get("/sources")
async def list_sources():
    current_user = "admin"
    db = SessionLocal()
    try:
        # 查询：属于当前用户 OR 属于 system 的文件
        docs = db.query(DocumentRecord).filter(
            (DocumentRecord.user_id == current_user) | 
            (DocumentRecord.user_id == "system")
        ).all()
        
        return [{
            "id": d.id, 
            "name": d.name, 
            "category": d.category # 前端可以根据这个字段给制度文件加个特殊的图标
        } for d in docs]
    finally:
        db.close()

@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    """处理前端‘添加来源’请求（改为同步阻塞式）"""
    if not file.filename.endswith(('.md', '.pdf', '.txt', '.docx')):
        raise HTTPException(status_code=400, detail="不支持的文件格式")

    current_user = "admin"
    
    # 传入上传目录和原始文件名，计算出最终的保存路径
    save_path = get_unique_path(UPLOAD_DIR, file.filename)
    unique_filename = save_path.name 
    file_id = unique_filename
    
    # 保存原始文件到磁盘
    try:
        with save_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件保存失败: {str(e)}")

    # 1. 在 SQLite 中创建元数据记录
    db = SessionLocal()
    try:
        new_doc = DocumentRecord(
            id=file_id,
            user_id=current_user,
            name=file.filename,
            path=str(save_path),
            category="user" 
        )
        db.add(new_doc)
        db.commit()
    finally:
        db.close()

    # 🟢 修改点 2：去掉 background_tasks.add_task，直接调用函数
    # 这样后端会一直卡在这里执行解析，等完全入库后才会执行下一行
    process_ingestion_task(
        file_id, 
        current_user, 
        save_path, 
        file.filename
    )
    
    # 🟢 修改点 3：状态改为 success
    return {"id": file_id, "name": file.filename, "status": "success"}

@router.delete("/sources/{file_id}")
async def delete_source(file_id: str):
    """物理删除来源及其向量分块"""
    current_user = "admin"
    db = SessionLocal()
    try:
        # 查找记录
        doc = db.query(DocumentRecord).filter(
            DocumentRecord.id == file_id, 
            DocumentRecord.user_id == current_user
        ).first()
        
        if not doc:
            raise HTTPException(status_code=404, detail="未找到该文档")

        # 1. 从向量库删除 (ChromaDB 支持按 metadata 过滤删除)
        vector_store.delete(where={"file_id": file_id})

        # 2. 删除本地物理文件
        if os.path.exists(doc.path):
            os.remove(doc.path)

        # 3. 从 SQLite 删除记录
        db.delete(doc)
        db.commit()
        
        return {"status": "success", "message": f"已移除 {doc.name}"}
    finally:
        db.close()


@router.get("/view/{filename}")
async def view_file(filename: str):
    """
    智能文件预览接口：
    1. 自动处理 URL 解码（解决中文文件名乱码问题）。
    2. 自动映射：如果请求 .temp.md 或 .md，优先尝试寻找同名的 .pdf。
    """
    # 1. 解码文件名 (防止 %E5%A4%A7%E6%95%B0%E6%8D%AE 这种乱码导致找不到文件)
    decoded_filename = urllib.parse.unquote(filename)
    
    # 2. 智能文件名修正逻辑
    target_filename = decoded_filename
    
    # 如果请求的是中间产物 .temp.md，强行指向 .pdf 原件
    if decoded_filename.endswith(".temp.md"):
        target_filename = decoded_filename.replace(".temp.md", ".pdf")
    
    # 如果请求的是普通 .md，但也可能是 PDF 转的，尝试找找有没有对应的 PDF
    elif decoded_filename.endswith(".md"):
        potential_pdf = decoded_filename.replace(".md", ".pdf")
        # 我们稍后在查找循环里验证它存不存在
        
    # 3. 定义查找路径
    search_dirs = [
        UPLOAD_DIR,           # data/uploads
        Path("data/system_docs") # data/system_docs
    ]
    
    final_path = None
    
    # 4. 双重查找循环
    # 策略：先找修正后的文件名 (PDF)，如果找不到，再找原始请求的文件名 (MD)
    filenames_to_try = [target_filename, decoded_filename]
    
    # 去重，防止 target 和 decoded 一样时找两次
    filenames_to_try = list(dict.fromkeys(filenames_to_try)) 

    for name in filenames_to_try:
        for directory in search_dirs:
            possible_path = directory / name
            if possible_path.exists():
                final_path = possible_path
                break
        if final_path:
            break
            
    # 5. 还是找不到？抛出异常
    if not final_path:
        print(f"❌ 文件未找到: 请求={filename}, 尝试查找={filenames_to_try}")
        raise HTTPException(status_code=404, detail=f"文件 '{decoded_filename}' 未找到")
    
    # 6. 确定返回类型
    # 如果是 PDF，浏览器会用内置阅读器打开
    # 如果是 Markdown，浏览器会直接显示文本
    media_type = "application/pdf" if final_path.suffix.lower() == ".pdf" else "text/plain"
    
    return FileResponse(
        path=final_path, 
        filename=final_path.name, 
        media_type=media_type,
        content_disposition_type="inline"
    )
