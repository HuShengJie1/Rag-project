import os
from pathlib import Path
from dotenv import load_dotenv

# 引入官方底层客户端
from llama_cloud import LlamaCloud

# 加载环境变量
load_dotenv()

# 全局复用 Client，避免每次调用都重新初始化
_LLAMA_CLIENT = None

def get_llama_client():
    global _LLAMA_CLIENT
    if _LLAMA_CLIENT is None:
        api_key = os.environ.get("LLAMA_CLOUD_API_KEY")
        if not api_key:
            raise ValueError("❌ 缺少 LLAMA_CLOUD_API_KEY 环境变量")
        _LLAMA_CLIENT = LlamaCloud(api_key=api_key)
    return _LLAMA_CLIENT

def _ensure_pdf_path(path: str | Path) -> Path:
    """校验路径是否存在且为 PDF 文件。"""
    pdf_path = Path(path)
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF 文件未找到: {pdf_path}")
    return pdf_path

def load_pdf_with_llamaparse(path: str | Path):
    """
    使用 LlamaCloud 解析 PDF 为带页码标记的 Markdown。
    返回的结构完全 1:1 兼容原有的 Marker 处理器。
    """
    pdf_path = _ensure_pdf_path(path)
    doc_name = pdf_path.name
    client = get_llama_client()

    print(f"🚀 [LlamaCloud] 正在使用 Agentic Plus 解析: {doc_name}")
    print("⏳ 正在请求云端处理，大模型正在阅读排版，请耐心等待...")

    parsed_data = []

    try:
        # 1. 核心解析请求
        # 建议使用 rb 模式打开文件传递给 SDK，确保文件流稳定上传
        with open(pdf_path, "rb") as f:
            result = client.parsing.parse(
                upload_file=f, 
                tier="agentic",
                version="latest",
                expand=['Markdown']
            )

        # 2. 遍历提取每一页，打上标记，并组装成目标字典结构
        for i, mk in enumerate(result.markdown.pages):
            page_num = i + 1
            
            # 严格按照你原有逻辑拼接页码锚点
            marked_text = (
                f"\n\n==== PAGE_{page_num}_START ====\n"
                f"{mk.markdown.strip()}\n"
                f"==== PAGE_{page_num}_END ====\n\n"
            )
            
            # ✨ 核心适配：组装成旧版 Marker load_pdf 完全一样的字典结构
            parsed_data.append({
                "doc_name": doc_name,
                "page": page_num,
                "text": marked_text,
                "section_path": None,
            })

        print(f"✅ [LlamaCloud] 解析完成！共提取 {len(parsed_data)} 页。")

    except Exception as exc:
        raise RuntimeError(f"❌ LlamaCloud 解析 PDF 失败: {pdf_path}") from exc

    return parsed_data

if __name__ == "__main__":
    # 快速测试代码
    try:
        # 请替换为你的实际测试 PDF 路径
        target_pdf = "data/raw/programs/大数据-2025级本科生培养方案-v13-724.pdf"
        results = load_pdf_with_llamaparse(target_pdf)
        
        if results:
            print(f"--- 预览解析结果 (Page {results[0]['page']}) ---")
            print(results[0]['text'][:500]) # 打印第一页的前500字符
    except Exception as e:
        print(f"❌ 运行测试出错: {e}")