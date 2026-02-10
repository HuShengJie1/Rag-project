from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import fitz  # 用于物理分页
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.output import text_from_rendered

__all__ = ["load_pdf"]

PageRecord = Dict[str, object]

# 全局转换器单例，避免重复加载数GB的模型
_MARKER_CONVERTER = None

def get_converter():
    global _MARKER_CONVERTER
    if _MARKER_CONVERTER is None:
        print("⏳ 正在初始化 Marker 模型字典（首次运行较慢）...")
        _MARKER_CONVERTER = PdfConverter(
            artifact_dict=create_model_dict(),
        )
    return _MARKER_CONVERTER

def _ensure_pdf_path(path: str | Path) -> Path:
    """校验路径是否存在且为 PDF 文件。"""
    pdf_path = Path(path)
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF 文件未找到: {pdf_path}")
    return pdf_path

def load_pdf(path: str | Path) -> List[PageRecord]:
    """
    使用 marker-pdf 逐页解析 PDF 并注入英文分页锚点。
    """
    pdf_path = _ensure_pdf_path(path)
    doc_name = pdf_path.name
    converter = get_converter()
    
    # 1. 打开原始 PDF 获取总页数
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    
    # 2. 创建临时目录存放单页 PDF
    temp_dir = Path("./temp_marker_processing")
    temp_dir.mkdir(exist_ok=True)
    
    records: List[PageRecord] = []
    
    try:
        for i in range(total_pages):
            page_num = i + 1
            print(f"🔄 [Marker] 正在处理 {doc_name} 第 {page_num}/{total_pages} 页...")

            # 3. 物理提取单页 PDF
            temp_pdf_path = temp_dir / f"{doc_name}_p{page_num}.pdf"
            single_page_doc = fitz.open()
            single_page_doc.insert_pdf(doc, from_page=i, to_page=i)
            single_page_doc.save(str(temp_pdf_path))
            single_page_doc.close()

            # 4. 调用 Marker 官方接口转换
            rendered = converter(str(temp_pdf_path))
            text, _, _ = text_from_rendered(rendered)
            
            # 5. 注入物理分页符 (使用英文分隔符，优化正则匹配)
            # 这种格式在处理中文长文档时非常稳健
            marked_text = (
                f"\n\n==== PAGE_{page_num}_START ====\n"
                f"{text.strip()}\n"
                f"==== PAGE_{page_num}_END ====\n\n"
            )

            records.append({
                "doc_name": doc_name,
                "page": page_num,
                "text": marked_text,
                "section_path": None,
            })

            # 删除临时单页文件
            temp_pdf_path.unlink()

    except Exception as exc:
        raise RuntimeError(f"Marker 解析 PDF 失败: {pdf_path}") from exc
    finally:
        # 清理工作
        doc.close()
        if temp_dir.exists():
            for f in temp_dir.glob("*"): f.unlink()
            temp_dir.rmdir()

    return records

if __name__ == "__main__":
    # 测试代码
    try:
        target_pdf = "data/raw/programs/大数据-2025级本科生培养方案-v13-724.pdf"
        results = load_pdf(target_pdf)
        for record in results[:2]: # 打印前两页看效果
            print(f"--- 预览解析结果 (Page {record['page']}) ---")
            print(record['text'])
    except Exception as e:
        print(f"❌ 运行测试出错: {e}")