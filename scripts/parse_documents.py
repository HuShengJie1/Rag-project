"""
统一批量解析脚本：
强制所有 PDF 经过 Marker-pdf 引擎处理，生成带页码标识的统一 Markdown 资产。
"""

from __future__ import annotations
import sys
from pathlib import Path
from typing import List

# 将 src 目录加入搜索路径
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

# 统一导入基于 Marker 的高精度加载器
from loaders.llamaparse_loader import load_pdf_with_llamaparse

def discover_pdfs(raw_root: Path) -> List[Path]:
    """递归发现 raw_root 下的全部 PDF 文件。"""
    return sorted(raw_root.rglob("*.pdf"))

def save_unified_markdown(records: List[dict], output_path: Path) -> None:
    """
    将解析记录保存为统一的 Markdown 文件。
    由于 load_pdf 已经注入了 ，此处仅需合并。
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # 使用三个换行符作为物理页之间的自然分隔
    content = "\n\n\n".join([str(rec.get("text", "")) for rec in records])
    
    output_path.write_text(content, encoding="utf-8")
    print(f"✅ 文件已保存: {output_path.relative_to(PROJECT_ROOT)}")

def process_single_file(pdf_path: Path, raw_root: Path, parsed_root: Path) -> None:
    """处理单个 PDF：加载、解析、落盘。"""
    # 所有输出统一存放在 md 子目录下
    rel_path = pdf_path.relative_to(raw_root)
    output_path = parsed_root / "md" / rel_path.with_suffix(".md")

    print(f"🚀 正在处理: {rel_path} ...")

    try:
        # 调用 Marker 引擎进行逐页解析
        # 这个函数内部已经处理了物理分页和锚点注入
        records = load_pdf_with_llamaparse(pdf_path)
        
        if records:
            save_unified_markdown(records, output_path)
        else:
            print(f"⚠️ 警告: {pdf_path.name} 未提取到任何内容。")

    except Exception as e:
        print(f"❌ 处理失败 {pdf_path.name}: {str(e)}")

def main() -> None:
    """主程序入口。"""
    raw_root = PROJECT_ROOT / "data" / "system_docs"
    parsed_root = PROJECT_ROOT / "data" / "parsed"

    # 1. 发现文件
    pdf_files = discover_pdfs(raw_root)
    if not pdf_files:
        print("📭 data/raw 目录下未找到 PDF 文件。")
        return

    print(f"📂 找到 {len(pdf_files)} 个待处理文档。")
    # print("🛠️ 采用统一 Marker-pdf 引擎进行高精度解析...")
    print("-" * 50)

    # 2. 循环处理
    for pdf_path in pdf_files:
        process_single_file(pdf_path, raw_root, parsed_root)

    print("-" * 50)
    print("🏁 所有解析任务已完成。")

if __name__ == "__main__":
    main()