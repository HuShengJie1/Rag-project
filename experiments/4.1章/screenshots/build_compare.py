#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
BASE = Path(__file__).resolve().parent
ASSETS = BASE / "assets"
DATA_DIR = BASE / "data"


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, cwd=ROOT)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def render_pdf_page(pdf_rel: str, page: int, output_name: str) -> str:
    pdf_path = ROOT / pdf_rel
    out_base = ASSETS / output_name
    ensure_dir(out_base.parent)
    run(
        [
            "pdftoppm",
            "-png",
            "-r",
            "160",
            "-f",
            str(page),
            "-l",
            str(page),
            "-singlefile",
            str(pdf_path),
            str(out_base),
        ]
    )
    return f"assets/{output_name}.png"


def page_items(json_rel: str, page_number: int) -> list[dict[str, Any]]:
    data = read_json(ROOT / json_rel)
    page_idx = page_number - 1
    return [item for item in data if item.get("page_idx") == page_idx]


def extract_table(items: list[dict[str, Any]], keyword: str | None = None) -> str | None:
    for item in items:
        if item.get("type") != "table":
            continue
        caption = " ".join(item.get("table_caption", [])) if isinstance(item.get("table_caption"), list) else str(item.get("table_caption", ""))
        if keyword is None or keyword in caption or keyword in str(item.get("table_body", "")):
            body = str(item.get("table_body", "")).strip()
            if body:
                return body
    return None


def extract_text_block(items: list[dict[str, Any]], limit: int = 8) -> str:
    lines: list[str] = []
    for item in items:
        if item.get("type") in {"page_number"}:
            continue
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        lines.append(text)
        if len(lines) >= limit:
            break
    return "\n\n".join(lines).strip()


def extract_equations(items: list[dict[str, Any]], limit: int = 2) -> list[str]:
    equations: list[str] = []
    for item in items:
        if item.get("type") != "equation":
            continue
        text = str(item.get("text", "")).strip()
        if text:
            equations.append(text)
        if len(equations) >= limit:
            break
    return equations


def trim_pdftotext_matrix(text_rel: str) -> str:
    text = read_text(ROOT / text_rel)
    start_marker = "毕业要求对培养目标的支撑关系矩阵"
    end_marker = "二、学制与学位"
    start = text.find(start_marker)
    end = text.find(end_marker)
    if start != -1:
        text = text[start:end if end != -1 and end > start else None]
    return text.strip()


def render_pre(text: str, missing: bool = False) -> str:
    if not text.strip():
        label = "缺失：未获得可用输出。"
        return f'<div class="missing-box">{html.escape(label)}</div>'
    cls = "mono-block missing" if missing else "mono-block"
    return f'<pre class="{cls}">{html.escape(text)}</pre>'


def render_table(title: str, table_html: str | None, extra_text: str | None = None, equations: list[str] | None = None) -> str:
    parts = [f'<div class="fragment-title">{html.escape(title)}</div>']
    if table_html:
        parts.append(f'<div class="table-wrap">{table_html}</div>')
    else:
        parts.append('<div class="missing-box">缺失：未找到对应表格结构。</div>')
    if extra_text:
        parts.append(f'<pre class="mono-block compact">{html.escape(extra_text)}</pre>')
    if equations:
        for idx, eq in enumerate(equations, start=1):
            parts.append(
                f'<div class="equation-label">公式片段 {idx}</div><pre class="mono-block equation">{html.escape(eq)}</pre>'
            )
    return "\n".join(parts)


def card(title: str, subtitle: str, body_html: str, summary: str, extra_class: str = "") -> str:
    classes = f"card {extra_class}".strip()
    return f"""
    <section class="{classes}">
      <header class="card-header">
        <h2>{html.escape(title)}</h2>
        <p class="card-subtitle">{html.escape(subtitle)}</p>
      </header>
      <div class="card-body">
        {body_html}
      </div>
      <footer class="card-footer">
        <span class="summary-label">小结</span>
        <span>{html.escape(summary)}</span>
      </footer>
    </section>
    """.strip()


def image_card(title: str, subtitle: str, image_rel: str, summary: str, frame_class: str) -> str:
    body = f"""
    <div class="image-frame {frame_class}">
      <img src="{html.escape(image_rel)}" alt="{html.escape(title)}">
    </div>
    """
    return card(title, subtitle, body, summary, "image-card")


def build_matrix_page() -> str:
    original_img = render_pdf_page(
        "data/system_docs/大数据-2025级本科生培养方案-v13-724.pdf",
        2,
        "bigdata_page2",
    )

    pdftotext_rel = "experiments/4.1章/generated/pdftotext/bigdata_plan/page_02.txt"
    pipeline_rel = (
        "experiments/embedding_experiment/parsing/outputs/pipeline/"
        "大数据-2025级本科生培养方案-v13-724__0e3d9ebe07/"
        "大数据-2025级本科生培养方案-v13-724/auto/"
        "大数据-2025级本科生培养方案-v13-724_content_list.json"
    )
    mineru_rel = (
        "experiments/embedding_experiment/parsing/outputs/vlm/"
        "大数据-2025级本科生培养方案-v13-724__0e3d9ebe07/"
        "大数据-2025级本科生培养方案-v13-724/hybrid_auto/"
        "大数据-2025级本科生培养方案-v13-724_content_list.json"
    )

    pipeline_items = page_items(pipeline_rel, 2)
    mineru_items = page_items(mineru_rel, 2)

    grid = [
        image_card(
            "原始 PDF 页面局部",
            "培养方案第 2 页，矩阵位于页面中下部。",
            original_img,
            "原页可见矩阵结构完整，是后续对比的参照基准。",
            "focus-matrix",
        ),
        card(
            "pdftotext -layout",
            "真实抽取结果，仅做基础排版，不修正文中问题。",
            render_pre(trim_pdftotext_matrix(pdftotext_rel)),
            "矩阵已线性化，行列关系被展开为普通文本。",
        ),
        card(
            "MinerU pipeline",
            "直接取自 pipeline 结构化输出中的矩阵表格。",
            render_table(
                "毕业要求对培养目标的支撑关系矩阵",
                extract_table(pipeline_items, "毕业要求对培养目标"),
            ),
            "已恢复表格外形，但个别勾选符号误识别为异常字符。",
        ),
        card(
            "MinerU2.5",
            "直接取自 MinerU2.5 VLM 输出中的矩阵表格。",
            render_table(
                "毕业要求对培养目标的支撑关系矩阵",
                extract_table(mineru_items, "毕业要求对培养目标"),
            ),
            "表格与勾选符号保持较完整，适合后续按表格语义切块。",
        ),
    ]

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>毕业要求支撑矩阵页面对比</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <main class="page">
    <header class="page-header">
      <h1>图 A：培养方案第 2 页“毕业要求支撑矩阵”本地解析对比</h1>
      <p>同一原始页面下，对比原始 PDF 局部、pdftotext -layout、MinerU pipeline 与 MinerU2.5 的真实输出差异。</p>
    </header>
    <section class="grid grid-4">
      {''.join(grid)}
    </section>
  </main>
</body>
</html>
"""


def build_mixed_page() -> str:
    page1_img = render_pdf_page(
        "data/system_docs/附件1-10 上海海洋大学信息学院课程质量评价办法.pdf",
        1,
        "quality_page1",
    )
    page4_img = render_pdf_page(
        "data/system_docs/附件1-10 上海海洋大学信息学院课程质量评价办法.pdf",
        4,
        "quality_page4",
    )

    pdftotext_page1 = ROOT / "experiments/4.1章/generated/pdftotext/course_quality_rules/page_01.txt"
    pipeline_rel = (
        "experiments/embedding_experiment/parsing/outputs/pipeline/"
        "附件1-10_上海海洋大学信息学院课程质量评价办法__2f8b91b22d/"
        "附件1-10 上海海洋大学信息学院课程质量评价办法/auto/"
        "附件1-10 上海海洋大学信息学院课程质量评价办法_content_list.json"
    )
    mineru_rel = (
        "experiments/embedding_experiment/parsing/outputs/vlm/"
        "附件1-10_上海海洋大学信息学院课程质量评价办法__2f8b91b22d/"
        "附件1-10 上海海洋大学信息学院课程质量评价办法/hybrid_auto/"
        "附件1-10 上海海洋大学信息学院课程质量评价办法_content_list.json"
    )

    mineru_page1_items = page_items(mineru_rel, 1)
    pipeline_page4_items = page_items(pipeline_rel, 4)
    mineru_page4_items = page_items(mineru_rel, 4)

    row1 = [
        image_card(
            "原始 PDF 第 1 页",
            "扫描型标题条款页，关注页眉、标题与一级条款。",
            page1_img,
            "原页包含页眉、公文号、主标题与条款标题，层次关系清晰。",
            "focus-top",
        ),
        card(
            "pdftotext -layout",
            "第 1 页真实输出结果。",
            render_pre(read_text(pdftotext_page1), missing=True),
            "该页输出为空，说明扫描页难以通过简单文本抽取得到可用结果。",
        ),
        card(
            "MinerU2.5",
            "第 1 页结构化文本摘录。",
            render_pre(extract_text_block(mineru_page1_items, limit=10)),
            "标题、条款顺序与正文边界基本保持，可直接据此划分章节块。",
        ),
    ]

    row2 = [
        image_card(
            "原始 PDF 第 4 页",
            "表格与公式混排页，关注表 1 及后续公式区域。",
            page4_img,
            "原页同时出现二维矩阵表与公式，适合观察复杂结构恢复能力。",
            "focus-formula",
        ),
        card(
            "MinerU pipeline",
            "第 4 页表格与公式摘录。",
            render_table(
                "表 1 课程目标与课程考核二维矩阵",
                extract_table(pipeline_page4_items, "表1"),
                extra_text=extract_text_block(pipeline_page4_items, limit=4),
                equations=extract_equations(pipeline_page4_items, limit=2),
            ),
            "表格主体可恢复，但公式内容明显失真，难以直接作为可用证据块。",
        ),
        card(
            "MinerU2.5",
            "第 4 页表格与公式摘录。",
            render_table(
                "表 1 课程目标与课程考核二维矩阵",
                extract_table(mineru_page4_items, "表1"),
                extra_text=extract_text_block(mineru_page4_items, limit=4),
                equations=extract_equations(mineru_page4_items, limit=2),
            ),
            "表格结构、公式编号与语义整体保持较好，更适合后续精细化切块。",
        ),
    ]

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>标题条款与公式表格混排页面对比</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <main class="page">
    <header class="page-header">
      <h1>图 B：制度办法复杂页面本地解析对比</h1>
      <p>第 1 行展示扫描型标题条款页，第 2 行展示表格与公式混排页，均使用项目中的真实输出结果。</p>
    </header>
    <section class="compare-row">
      <div class="row-header">
        <h2>第 1 行：制度办法第 1 页，标题条款页</h2>
      </div>
      <div class="grid grid-3">
        {''.join(row1)}
      </div>
    </section>
    <section class="compare-row">
      <div class="row-header">
        <h2>第 2 行：制度办法第 4 页，公式与表格混排页</h2>
      </div>
      <div class="grid grid-3">
        {''.join(row2)}
      </div>
    </section>
  </main>
</body>
</html>
"""


def write(path: Path, content: str) -> None:
    ensure_dir(path.parent)
    path.write_text(content, encoding="utf-8")


def markdown_code_block(text: str, language: str = "") -> str:
    fence = f"```{language}".rstrip()
    return f"{fence}\n{text.rstrip()}\n```"


def markdown_table_block(title: str, table_html: str | None) -> str:
    if table_html:
        return f"### {title}\n\n{table_html}\n"
    return f"### {title}\n\n**缺失：未找到对应表格结构。**\n"


def build_matrix_markdown() -> str:
    pdftotext_rel = "experiments/4.1章/generated/pdftotext/bigdata_plan/page_02.txt"
    pipeline_rel = (
        "experiments/embedding_experiment/parsing/outputs/pipeline/"
        "大数据-2025级本科生培养方案-v13-724__0e3d9ebe07/"
        "大数据-2025级本科生培养方案-v13-724/auto/"
        "大数据-2025级本科生培养方案-v13-724_content_list.json"
    )
    mineru_rel = (
        "experiments/embedding_experiment/parsing/outputs/vlm/"
        "大数据-2025级本科生培养方案-v13-724__0e3d9ebe07/"
        "大数据-2025级本科生培养方案-v13-724/hybrid_auto/"
        "大数据-2025级本科生培养方案-v13-724_content_list.json"
    )
    pipeline_items = page_items(pipeline_rel, 2)
    mineru_items = page_items(mineru_rel, 2)

    pdftotext_block = markdown_code_block(trim_pdftotext_matrix(pdftotext_rel), "text")
    pipeline_table = markdown_table_block(
        "毕业要求对培养目标的支撑关系矩阵（MinerU pipeline）",
        extract_table(pipeline_items, "毕业要求对培养目标"),
    )
    mineru_table = markdown_table_block(
        "毕业要求对培养目标的支撑关系矩阵（MinerU2.5）",
        extract_table(mineru_items, "毕业要求对培养目标"),
    )

    return f"""# 图 A（Markdown 版）：培养方案第 2 页“毕业要求支撑矩阵”对比

本页保留真实结果，仅将展示形式改为 Markdown，以便在支持数学公式与 HTML 表格的 Markdown 预览器中直接渲染。

## 原始 PDF 页面局部

![培养方案第 2 页原始页面局部](assets/bigdata_page2.png)

小结：原页中的矩阵结构完整，是判断后续解析结果是否保留行列关系的参照基准。

## pdftotext -layout

{pdftotext_block}

小结：矩阵已线性化，虽然字符仍在，但“毕业要求-培养目标”的对应关系退化为普通文本顺序。

## MinerU pipeline

{pipeline_table}

小结：已恢复表格外形，但局部勾选符号存在误识别，例如“专”“~”等异常字符。

## MinerU2.5

{mineru_table}

小结：表格结构和勾选符号保持较完整，更适合作为后续表格块切分与元数据绑定的输入。
"""


def build_mixed_markdown() -> str:
    pdftotext_page1 = ROOT / "experiments/4.1章/generated/pdftotext/course_quality_rules/page_01.txt"
    pipeline_rel = (
        "experiments/embedding_experiment/parsing/outputs/pipeline/"
        "附件1-10_上海海洋大学信息学院课程质量评价办法__2f8b91b22d/"
        "附件1-10 上海海洋大学信息学院课程质量评价办法/auto/"
        "附件1-10 上海海洋大学信息学院课程质量评价办法_content_list.json"
    )
    mineru_rel = (
        "experiments/embedding_experiment/parsing/outputs/vlm/"
        "附件1-10_上海海洋大学信息学院课程质量评价办法__2f8b91b22d/"
        "附件1-10 上海海洋大学信息学院课程质量评价办法/hybrid_auto/"
        "附件1-10 上海海洋大学信息学院课程质量评价办法_content_list.json"
    )

    mineru_page1_items = page_items(mineru_rel, 1)
    pipeline_page4_items = page_items(pipeline_rel, 4)
    mineru_page4_items = page_items(mineru_rel, 4)

    page1_text = extract_text_block(mineru_page1_items, limit=10)
    pipeline_eqs = extract_equations(pipeline_page4_items, limit=2)
    mineru_eqs = extract_equations(mineru_page4_items, limit=2)

    missing_block = "**缺失：`pdftotext -layout` 第 1 页真实输出为空。**"
    pipeline_eq_block = "\n\n".join(
        markdown_code_block(eq, "latex") for eq in pipeline_eqs
    )
    mineru_eq_block = "\n\n".join(mineru_eqs)

    return f"""# 图 B（Markdown 版）：制度办法复杂页面对比

本页分为两部分：第一部分展示第 1 页的扫描型标题条款页，第二部分展示第 4 页的公式与表格混排页。

## 第一部分：制度办法第 1 页，标题条款页

### 原始 PDF 页面

![制度办法第 1 页原始页面](assets/quality_page1.png)

小结：原页可见页眉、公文号、主标题与条款标题，层次关系明确。

### pdftotext -layout

{missing_block}

小结：简单文本抽取在该扫描页上未获得可用结果。

### MinerU2.5

{markdown_code_block(page1_text, "text")}

小结：标题、条款顺序与正文边界基本保持，适合按章节边界组织语义块。

## 第二部分：制度办法第 4 页，公式与表格混排页

### 原始 PDF 页面

![制度办法第 4 页原始页面](assets/quality_page4.png)

小结：原页同时出现矩阵表格与课程目标达成公式，是典型复杂结构页面。

### MinerU pipeline

{markdown_table_block("表 1 课程目标与课程考核二维矩阵（MinerU pipeline）", extract_table(pipeline_page4_items, "表1"))}

以下公式片段保留为原始 LaTeX 文本，以体现 pipeline 输出的失真特征：

{pipeline_eq_block if pipeline_eq_block else "**缺失：未找到 pipeline 公式片段。**"}

小结：表格主体可恢复，但公式内容明显失真，难以直接作为可用证据块。

### MinerU2.5

{markdown_table_block("表 1 课程目标与课程考核二维矩阵（MinerU2.5）", extract_table(mineru_page4_items, "表1"))}

以下公式片段直接保留为数学块，便于 Markdown 预览器渲染：

{mineru_eq_block if mineru_eq_block else "**缺失：未找到 MinerU2.5 公式片段。**"}

小结：表格结构、公式编号与公式语义整体保持较好，更适合作为后续精细化切块的输入。
"""


def main() -> None:
    ensure_dir(ASSETS)
    ensure_dir(DATA_DIR)

    matrix_html = build_matrix_page()
    mixed_html = build_mixed_page()
    matrix_md = build_matrix_markdown()
    mixed_md = build_mixed_markdown()

    write(BASE / "parser_matrix_compare.html", matrix_html)
    write(BASE / "parser_mixed_compare.html", mixed_html)
    write(BASE / "parser_matrix_compare.md", matrix_md)
    write(BASE / "parser_mixed_compare.md", mixed_md)

    index = {
        "figures": {
            "parser_matrix_compare.html": {
                "target": "图 A：培养方案第 2 页毕业要求支撑矩阵对比",
                "sources": [
                    "data/system_docs/大数据-2025级本科生培养方案-v13-724.pdf#page=2",
                    "experiments/4.1章/generated/pdftotext/bigdata_plan/page_02.txt",
                    "experiments/embedding_experiment/parsing/outputs/pipeline/大数据-2025级本科生培养方案-v13-724__0e3d9ebe07/大数据-2025级本科生培养方案-v13-724/auto/大数据-2025级本科生培养方案-v13-724_content_list.json",
                    "experiments/embedding_experiment/parsing/outputs/vlm/大数据-2025级本科生培养方案-v13-724__0e3d9ebe07/大数据-2025级本科生培养方案-v13-724/hybrid_auto/大数据-2025级本科生培养方案-v13-724_content_list.json",
                ],
            },
            "parser_matrix_compare.md": {
                "target": "图 A：培养方案第 2 页毕业要求支撑矩阵对比（Markdown 版）"
            },
            "parser_mixed_compare.html": {
                "target": "图 B：制度办法第 1 页与第 4 页复杂结构页面对比",
                "sources": [
                    "data/system_docs/附件1-10 上海海洋大学信息学院课程质量评价办法.pdf#page=1",
                    "data/system_docs/附件1-10 上海海洋大学信息学院课程质量评价办法.pdf#page=4",
                    "experiments/4.1章/generated/pdftotext/course_quality_rules/page_01.txt",
                    "experiments/embedding_experiment/parsing/outputs/pipeline/附件1-10_上海海洋大学信息学院课程质量评价办法__2f8b91b22d/附件1-10 上海海洋大学信息学院课程质量评价办法/auto/附件1-10 上海海洋大学信息学院课程质量评价办法_content_list.json",
                    "experiments/embedding_experiment/parsing/outputs/vlm/附件1-10_上海海洋大学信息学院课程质量评价办法__2f8b91b22d/附件1-10 上海海洋大学信息学院课程质量评价办法/hybrid_auto/附件1-10 上海海洋大学信息学院课程质量评价办法_content_list.json",
                ],
                "pdftotext_page1_status": "empty",
            },
            "parser_mixed_compare.md": {
                "target": "图 B：制度办法第 1 页与第 4 页复杂结构页面对比（Markdown 版）"
            },
        }
    }
    write(DATA_DIR / "render_index.json", json.dumps(index, ensure_ascii=False, indent=2) + "\n")
    print("已生成 HTML 对比页与素材索引。")


if __name__ == "__main__":
    main()
