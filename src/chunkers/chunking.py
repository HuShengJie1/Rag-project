"""
基于 LangChain 的增强型分块模块（NotebookLM 适配版）。
新增：file_id 与 user_id 的元数据注入，支持多租户逻辑隔离。
"""

from __future__ import annotations
import re
from pathlib import Path
from typing import Dict, List, Any

# 注意：langchain_text_splitters 需要安装 langchain 库
# pip install langchain
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

__all__ = ["chunk_markdown_file"]

Chunk = Dict[str, Any]

def _build_chunk(
    source_file: Path,
    text: str,
    seq: int,
    metadata: Dict[str, Any] | None = None,
) -> Chunk:
    """构造增强型 chunk 字典结构。"""
    meta = {
        "source": source_file.name,
        "chunk_seq": seq,
        "file_path": str(source_file),
        **(metadata or {}) # 这里会包含 file_id 和 user_id
    }
    chunk_id = f"{source_file.stem}#{seq}"
    return {
        "chunk_id": chunk_id,
        "text": text,
        "metadata": meta,
    }

def _md_header_splitter() -> MarkdownHeaderTextSplitter:
    # 定义 Markdown 标题层级
    headers = [("#", "h1"), ("##", "h2"), ("###", "h3")]
    return MarkdownHeaderTextSplitter(headers_to_split_on=headers)

def _recursive_splitter(chunk_size: int = 1300, chunk_overlap: int = 300) -> RecursiveCharacterTextSplitter:
    # 递归字符分割器
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", "。", "！", "？", "；", " ", ""],
    )

def _clean_text_density(text: str) -> str:
    """对 Markdown 文本进行脱水，提高信息密度。"""
    # 移除表格多余空格
    lines = []
    for line in text.splitlines():
        if '|' in line:
            lines.append(re.sub(r'\s+', ' ', line.strip()))
        else:
            lines.append(line.strip())
    
    text = "\n".join(lines)
    text = re.sub(r'\n{3,}', '\n\n', text) # 将3个以上换行符合并为2个
    return text.strip()

# --- 核心修改：增加 file_id 和 user_id 参数 ---

def chunk_markdown_file(
    path: Path, 
    file_id: str = "unknown", 
    user_id: str = "admin", 
    chunk_size: int = 1300, 
    chunk_overlap: int = 400
) -> List[Chunk]:
    """
    处理带页码锚点的 Markdown 文件：
    1. 注入 file_id 和 user_id 以实现 NotebookLM 的逻辑隔离。
    2. 按标题层级回填至正文，增强表格等非结构化数据的检索精度。
    """
    try:
        raw_text = path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"读取文件失败: {path}, error: {e}")
        return []

    text = _clean_text_density(raw_text)
    
    # 实例化分割器
    header_splitter = _md_header_splitter()
    length_splitter = _recursive_splitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    # 1. 语义分块 (按 Header 切分)
    # 注意：MarkdownHeaderTextSplitter 会移除 Header 行，并将 Header 内容放入 metadata
    docs = header_splitter.split_text(text)
    
    chunks: List[Chunk] = []
    seq = 1
    last_seen_page = 1 

    for doc in docs:
        # 提取标题前缀 (例如: "第一章 > 第一节")
        header_values = [str(v) for v in doc.metadata.values()]
        header_prefix = f"【{' > '.join(header_values)}】\n" if header_values else ""
        
        # 2. 长度二次切分
        sub_docs = length_splitter.split_documents([doc])
        
        for sub in sub_docs:
            content_with_header = header_prefix + sub.page_content
            
            # 3. 页码追踪 (从 Markdown 中提取 ==== PAGE_1_START ==== 标记)
            page_matches = re.findall(r'==== PAGE_(\d+)_START ====', content_with_header)
            if page_matches:
                # 提取切片中包含的所有页码
                current_pages = sorted(list(set(int(p) for p in page_matches)))
                page_labels = current_pages
                if current_pages:
                    last_seen_page = current_pages[-1]
            else:
                # 如果当前切片没有页码标记，延续上一页
                page_labels = [last_seen_page]

            # 4. 噪声清理 (移除页码标记)
            clean_text = re.sub(r'==== PAGE_\d+_(START|END) ====', '', content_with_header).strip()
            
            # 🟢 5. 核心修改：上下文注入 (Context Injection)
            # 在文本开头强行加上文件名，解决“上下文丢失”问题
            # 这样向量搜索时，即使切片内部没有“大数据专业”字样，也能通过开头匹配到
            enhanced_text = f"【来源文档：{path.name}】\n{clean_text}"

            # 6. 组装并注入身份元数据
            chunks.append(
                _build_chunk(
                    source_file=path,
                    text=enhanced_text,  # 👈 使用增强后的文本
                    seq=seq,
                    metadata={
                        "file_id": file_id,   # 👈 记录属于哪个文件
                        "user_id": user_id,   # 👈 记录属于哪个用户
                        "headers": header_values,
                        "page_labels": page_labels,
                        "doc_name": path.name # 额外存一个字段方便查看
                    },
                )
            )
            seq += 1
            
    return chunks