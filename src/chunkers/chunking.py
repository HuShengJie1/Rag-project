"""基于 LangChain 的增强型分块模块。
已更新：支持标题回填（Header Prepending）以增强语义检索精度。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Sequence

from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

__all__ = ["chunk_markdown_file", "chunk_all_documents"]

Chunk = Dict[str, object]

def _build_chunk(
    source_file: Path,
    text: str,
    seq: int,
    metadata: Dict[str, object] | None = None,
) -> Chunk:
    """构造增强型 chunk 字典结构。"""
    meta = {
        "source": source_file.name,
        "chunk_seq": seq,
        "file_path": str(source_file),
        **(metadata or {})
    }
    chunk_id = f"{source_file.stem}#{seq}"
    return {
        "chunk_id": chunk_id,
        "text": text,
        "metadata": meta,
    }

def _md_header_splitter() -> MarkdownHeaderTextSplitter:
    """按工程认证文档常用的三级标题进行初步语义拆分。"""
    headers = [("#", "h1"), ("##", "h2"), ("###", "h3")]
    return MarkdownHeaderTextSplitter(headers_to_split_on=headers)

def _recursive_splitter(chunk_size: int = 800, chunk_overlap: int = 150) -> RecursiveCharacterTextSplitter:
    """递归字符分割器，优先保证中文句子的完整性。"""
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", "。", "！", "？", "；", " ", ""],
    )

def _clean_table_whitespace(text: str) -> str:
    """专门针对 Markdown 表格单元格内的多余空格进行脱水。"""
    lines = []
    for line in text.splitlines():
        if '|' in line:
            parts = line.split('|')
            cleaned_parts = [re.sub(r'\s+', ' ', p.strip()) for p in parts]
            new_line = "|".join(cleaned_parts)
            lines.append(new_line)
        else:
            lines.append(line)
    return "\n".join(lines)

def _clean_text_density(text: str) -> str:
    """对 Markdown 文本进行“脱水”处理，提高信息密度。"""
    text = _clean_table_whitespace(text)
    text = "\n".join([line.strip() for line in text.splitlines()])
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.replace("<br>", " ")
    return text.strip()

# --- 核心修改部分：chunk_markdown_file ---

def chunk_markdown_file(path: Path, chunk_size: int = 1300, chunk_overlap: int = 400) -> List[Chunk]:
    """
    处理带页码锚点的 Markdown 文件：
    1. 按标题层级做初步切分。
    2. 构造标题前缀并回填至正文。
    3. 按字符长度做二次切分。
    4. 实时捕获页码并清理锚点。
    """
    raw_text = path.read_text(encoding="utf-8")
    
    text = _clean_text_density(raw_text)
    header_splitter = _md_header_splitter()
    length_splitter = _recursive_splitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    # 1. 语义分块（MarkdownHeaderTextSplitter 会将标题存入 metadata）
    docs = header_splitter.split_text(text)
    
    chunks: List[Chunk] = []
    seq = 1
    last_seen_page = 1 

    for doc in docs:
        # --- [新增] 标题回填逻辑 ---
        # 提取当前分块所属的所有层级标题，构造如 "【标题1 > 标题2】\n" 的前缀
        header_values = [str(v) for v in doc.metadata.values()]
        header_prefix = f"【{' > '.join(header_values)}】\n" if header_values else ""
        
        # 2. 长度分块：对已经带有标题属性的文档进行精细切分
        sub_docs = length_splitter.split_documents([doc])
        
        for sub in sub_docs:
            # --- [修改] 将标题前缀拼接到每个子分块的正文开头 ---
            # 这样向量模型就能检索到“标题”中的关键词了
            raw_content = sub.page_content
            content_with_header = header_prefix + raw_content
            
            # 3. 页码追踪
            page_matches = re.findall(r'==== PAGE_(\d+)_START ====', content_with_header)
            
            if page_matches:
                page_labels = sorted(list(set(int(p) for p in page_matches)))
                last_seen_page = page_labels[-1]
            else:
                page_labels = [last_seen_page]

            # 4. 正文清理：剔除锚点噪声，保留标题前缀和纯净正文
            clean_text = re.sub(r'==== PAGE_\d+_(START|END) ====', '', content_with_header).strip()
            
            # 5. 组装 Chunk
            chunks.append(
                _build_chunk(
                    source_file=path,
                    text=clean_text,
                    seq=seq,
                    metadata={
                        "headers": header_values,
                        "page_labels": page_labels,
                        "is_cross_page": len(page_labels) > 1
                    },
                )
            )
            seq += 1
            
    return chunks

# --- 后续函数保持不变 ---

def chunk_all_documents(
    md_root: Path | None = None,
    chunk_size: int = 1000,
    chunk_overlap: int = 250,
) -> List[Chunk]:
    project_root = Path(__file__).resolve().parent.parent.parent 
    md_root = md_root or (project_root / "data" / "parsed" / "md")
    all_chunks: List[Chunk] = []
    md_files = sorted(md_root.rglob("*.md"))
    for md_file in md_files:
        all_chunks.extend(chunk_markdown_file(md_file, chunk_size=chunk_size, chunk_overlap=chunk_overlap))
    return all_chunks

if __name__ == "__main__":
    chunks = chunk_all_documents()
    if chunks:
        print(f"📊 样例分块内容预览:\n{chunks[0]['text'][:200]}...")
    print(f"✅ 处理完成，总分块数: {len(chunks)}")