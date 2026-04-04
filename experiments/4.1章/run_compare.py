#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
EXP_DIR = Path(__file__).resolve().parent
GENERATED_DIR = EXP_DIR / "generated"
PARSING_DIR = REPO_ROOT / "experiments" / "embedding_experiment" / "parsing"


DOCUMENTS = [
    {
        "slug": "bigdata_plan",
        "title": "大数据本科培养方案",
        "file_name": "大数据-2025级本科生培养方案-v13-724.pdf",
        "pdf_relpath": "data/system_docs/大数据-2025级本科生培养方案-v13-724.pdf",
        "focus_pages": [2, 4],
        "page_notes": {
            2: "毕业要求对培养目标的支撑关系矩阵，重点观察矩阵表格结构与勾选符号保留情况。",
            4: "课程设置相关表格集中出现，重点观察列结构、表头与阅读顺序。",
        },
    },
    {
        "slug": "course_quality_rules",
        "title": "课程质量评价办法",
        "file_name": "附件1-10 上海海洋大学信息学院课程质量评价办法.pdf",
        "pdf_relpath": "data/system_docs/附件1-10 上海海洋大学信息学院课程质量评价办法.pdf",
        "focus_pages": [1, 4],
        "page_notes": {
            1: "标题与一级条款混排，重点观察扫描件下标题层级恢复能力。",
            4: "表格与公式混排，重点观察公式可读性与结构保持能力。",
        },
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="为论文 4.1 章整理本地解析对比材料。"
    )
    parser.add_argument(
        "--only-doc",
        choices=[doc["slug"] for doc in DOCUMENTS],
        help="仅处理指定文档。",
    )
    parser.add_argument(
        "--skip-pdftotext",
        action="store_true",
        help="跳过 pdftotext 基线生成，仅整理既有 MinerU 结果。",
    )
    return parser.parse_args()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_manifest(profile: str) -> dict[str, dict[str, str]]:
    manifest_path = PARSING_DIR / f"manifest.{profile}.csv"
    rows: dict[str, dict[str, str]] = {}
    with manifest_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows[row["file_name"]] = row
    return rows


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_text(path: Path, content: str) -> None:
    ensure_dir(path.parent)
    path.write_text(content, encoding="utf-8")


def clean_text(text: str) -> str:
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    lines = [line.rstrip() for line in text.splitlines()]
    return "\n".join(lines).strip()


def format_item(item: dict[str, Any], index: int) -> str:
    item_type = item.get("type", "unknown")
    text = clean_text(str(item.get("text", "")))
    header = f"## 条目 {index:02d} | 类型：{item_type}"
    extras: list[str] = []

    if item.get("text_level") is not None:
        extras.append(f"- 文本层级：{item['text_level']}")

    if text:
        extras.append("- 文本内容：")
        extras.append(text)

    table_caption = clean_text(str(item.get("table_caption", "")))
    if table_caption:
        extras.append("- 表格标题：")
        extras.append(table_caption)

    table_body = clean_text(str(item.get("table_body", "")))
    if table_body:
        extras.append("- 表格内容：")
        extras.append("```html")
        extras.append(table_body)
        extras.append("```")

    latex = clean_text(str(item.get("latex", "")))
    if latex:
        extras.append("- 公式内容：")
        extras.append("```latex")
        extras.append(latex)
        extras.append("```")

    return "\n".join([header, *extras]).strip()


def export_page_snippet(
    content_list_path: Path,
    output_path: Path,
    page_number: int,
    title: str,
    profile_label: str,
) -> dict[str, Any]:
    data = read_json(content_list_path)
    page_idx = page_number - 1
    items = [item for item in data if item.get("page_idx") == page_idx]

    lines = [
        f"# {title} 第 {page_number} 页页级摘录",
        "",
        f"- 解析方案：{profile_label}",
        f"- 来源文件：{content_list_path.relative_to(REPO_ROOT)}",
        f"- 页面编号：{page_number}",
        f"- 条目数量：{len(items)}",
        "",
    ]

    for idx, item in enumerate(items, start=1):
        lines.append(format_item(item, idx))
        lines.append("")

    write_text(output_path, "\n".join(lines).rstrip() + "\n")
    return {
        "page_number": page_number,
        "item_count": len(items),
        "output_path": str(output_path.relative_to(REPO_ROOT)),
    }


def run_pdftotext(pdf_path: Path, doc_slug: str) -> dict[str, Any]:
    output_dir = GENERATED_DIR / "pdftotext" / doc_slug
    ensure_dir(output_dir)
    full_text_path = output_dir / "full.txt"

    pdftotext_bin = shutil.which("pdftotext")
    if not pdftotext_bin:
        return {
            "status": "missing_tool",
            "message": "未找到 pdftotext，未生成纯文本基线。",
        }

    command = [pdftotext_bin, "-layout", str(pdf_path), str(full_text_path)]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return {
            "status": "error",
            "message": (result.stderr or result.stdout or "pdftotext 执行失败").strip(),
        }

    full_text = full_text_path.read_text(encoding="utf-8", errors="ignore")
    pages = full_text.split("\f")
    page_files: list[str] = []
    for page_no, page_text in enumerate(pages, start=1):
        cleaned = page_text.strip()
        if page_no == len(pages) and not cleaned:
            continue
        page_path = output_dir / f"page_{page_no:02d}.txt"
        write_text(page_path, cleaned + ("\n" if cleaned else ""))
        page_files.append(str(page_path.relative_to(REPO_ROOT)))

    return {
        "status": "success",
        "full_text_path": str(full_text_path.relative_to(REPO_ROOT)),
        "page_files": page_files,
    }


def build_doc_index(
    doc: dict[str, Any],
    pipeline_manifest: dict[str, dict[str, str]],
    vlm_manifest: dict[str, dict[str, str]],
    skip_pdftotext: bool,
) -> dict[str, Any]:
    pdf_path = REPO_ROOT / doc["pdf_relpath"]
    if not pdf_path.exists():
        raise FileNotFoundError(f"未找到 PDF: {pdf_path}")

    file_name = doc["file_name"]
    pipeline_entry = pipeline_manifest.get(file_name)
    vlm_entry = vlm_manifest.get(file_name)

    doc_output_dir = GENERATED_DIR / "snippets" / doc["slug"]
    ensure_dir(doc_output_dir)

    doc_index: dict[str, Any] = {
        "slug": doc["slug"],
        "title": doc["title"],
        "pdf_relpath": doc["pdf_relpath"],
        "focus_pages": doc["focus_pages"],
        "page_notes": doc["page_notes"],
        "pipeline": None,
        "mineru25": None,
        "pdftotext": None,
    }

    if pipeline_entry:
        pipeline_md_path = Path(pipeline_entry["output_md_path"])
        pipeline_json_path = pipeline_md_path.with_name(
            pipeline_md_path.stem + "_content_list.json"
        )
        page_exports = []
        for page_number in doc["focus_pages"]:
            output_path = doc_output_dir / f"pipeline_page_{page_number:02d}.md"
            page_exports.append(
                export_page_snippet(
                    pipeline_json_path,
                    output_path,
                    page_number,
                    doc["title"],
                    "MinerU pipeline",
                )
            )
        doc_index["pipeline"] = {
            "md_path": str(pipeline_md_path.relative_to(REPO_ROOT)),
            "content_list_path": str(pipeline_json_path.relative_to(REPO_ROOT)),
            "page_exports": page_exports,
        }

    if vlm_entry:
        vlm_md_path = Path(vlm_entry["output_md_path"])
        vlm_json_path = vlm_md_path.with_name(vlm_md_path.stem + "_content_list.json")
        page_exports = []
        for page_number in doc["focus_pages"]:
            output_path = doc_output_dir / f"mineru25_page_{page_number:02d}.md"
            page_exports.append(
                export_page_snippet(
                    vlm_json_path,
                    output_path,
                    page_number,
                    doc["title"],
                    "MinerU2.5 VLM",
                )
            )
        doc_index["mineru25"] = {
            "md_path": str(vlm_md_path.relative_to(REPO_ROOT)),
            "content_list_path": str(vlm_json_path.relative_to(REPO_ROOT)),
            "page_exports": page_exports,
        }

    if not skip_pdftotext:
        doc_index["pdftotext"] = run_pdftotext(pdf_path, doc["slug"])

    return doc_index


def main() -> None:
    args = parse_args()
    ensure_dir(GENERATED_DIR)

    pipeline_manifest = load_manifest("pipeline")
    vlm_manifest = load_manifest("vlm")

    selected_docs = DOCUMENTS
    if args.only_doc:
        selected_docs = [doc for doc in DOCUMENTS if doc["slug"] == args.only_doc]

    index: dict[str, Any] = {"documents": []}
    for doc in selected_docs:
        index["documents"].append(
            build_doc_index(doc, pipeline_manifest, vlm_manifest, args.skip_pdftotext)
        )

    index_path = GENERATED_DIR / "index.json"
    write_text(index_path, json.dumps(index, ensure_ascii=False, indent=2) + "\n")
    print(f"已生成索引: {index_path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
