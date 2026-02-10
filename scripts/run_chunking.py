"""批量对解析后的 Markdown 执行分块，并以 JSON Lines 落盘。

支持跨页页码追踪，并自动识别子目录作为文档类别。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Iterable, List

# 1. 修正路径逻辑：假设脚本在 src/某个子目录下，向上跳三级到达根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from chunkers.chunking import chunk_markdown_file  # 仅保留 Markdown 分块器

def discover_markdown_files(root: Path) -> List[Path]:
    """
    使用 rglob 递归发现所有子目录（如 programs, standards）下的 .md 文件。
    """
    if not root.exists():
        print(f"⚠️ 警告：路径不存在 {root}")
        return []
    # 递归搜索所有层级的 .md 文件
    return sorted(p for p in root.rglob("*.md") if p.is_file())

def save_chunks_jsonl(chunks: Iterable[dict], output_path: Path) -> None:
    """将 chunk 列表写入 JSON Lines 文件，确认为 UTF-8 编码。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for chunk in chunks:
            # ensure_ascii=False 保证中文不被转义，方便调试查看
            f.write(json.dumps(chunk, ensure_ascii=False))
            f.write("\n")

def main() -> None:
    """命令行入口：遍历解析后的目录并执行分块。"""
    # 统一后的 Markdown 根目录
    md_root = PROJECT_ROOT / "data" / "parsed" / "md"
    output_path = PROJECT_ROOT / "data" / "chunks" / "all_chunks.jsonl"

    print(f"🔍 正在扫描目录: {md_root}")
    md_files = discover_markdown_files(md_root)
    
    if not md_files:
        print("❌ 未找到任何待处理的 Markdown 文件，请检查路径。")
        return

    all_chunks = []
    
    for md_file in md_files:
        # 自动提取类别：例如 data/parsed/md/programs/xxx.md -> category = programs
        category = md_file.parent.name if md_file.parent != md_root else "general"
        
        print(f"📦 正在分块 [{category}]: {md_file.name}")
        
        # 调用我们之前更新的、支持页码锚点识别的 chunk_markdown_file
        try:
            file_chunks = chunk_markdown_file(md_file)
            
            # 注入类别信息到元数据，支持后续的高级检索过滤 
            for c in file_chunks:
                c["metadata"]["category"] = category
                
            all_chunks.extend(file_chunks)
        except Exception as e:
            print(f"❌ 处理文件 {md_file.name} 时出错: {e}")

    # 落盘
    if all_chunks:
        save_chunks_jsonl(all_chunks, output_path)
        print("-" * 50)
        print(f"✅ 处理完成！")
        print(f"📊 总分块数: {len(all_chunks)}")
        print(f"💾 输出路径: {output_path.relative_to(PROJECT_ROOT)}")
    else:
        print("分块结果为空，请检查 Markdown 内部格式。")

if __name__ == "__main__":
    main()