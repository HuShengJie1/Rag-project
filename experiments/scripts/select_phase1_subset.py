from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


PARSER_PRIORITY = ["marker", "pymupdf4llm", "pdfplumber", "unstructured", "llamaparse", "pymupdf"]


@dataclass
class DocFeatures:
    doc_id: str
    doc_dir: str
    source_pdf: str
    doc_type_raw: str
    doc_type_inferred: str
    page_count: int = 0
    table_rich: str = "need_manual_review"
    scanned: str = "need_manual_review"
    structure_complex: str = "need_manual_review"
    need_manual_review: bool = False
    selected: bool = False
    recommendation_score: float = 0.0
    recommendation_reason: str = ""
    marker_text_length: int = 0
    pymupdf_text_length: int = 0
    llamaparse_text_length: int = 0
    table_cells: int = 0
    table_blocks: int = 0
    section_headers: int = 0
    picture_blocks: int = 0
    unique_block_types: int = 0
    ocr_pages: int = 0
    pdftext_pages: int = 0
    pipe_table_lines: int = 0
    confidence_notes: list[str] = field(default_factory=list)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Select representative Phase 1 parsing evaluation subset.")
    parser.add_argument("--manifest", type=str, default="experiments/parsing_eval/manifest.csv")
    parser.add_argument("--output-csv", type=str, default="experiments/parsing_eval/phase1_subset.csv")
    parser.add_argument("--output-report", type=str, default="experiments/parsing_eval/phase1_subset_report.md")
    parser.add_argument("--target-size", type=int, default=12)
    parser.add_argument("--exclude-doc-ids", type=str, default="", help="Comma separated doc_ids to exclude")
    return parser.parse_args()


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def normalize_doc_type(raw: str, doc_dir: str) -> tuple[str, bool]:
    text = " ".join([raw or "", doc_dir or ""]).lower()
    if "教学大纲" in text or "syllabus" in text:
        return "syllabus", True
    if "培养方案" in text or "人才培养方案" in text or "training program" in text:
        return "training_program", True
    if "达成" in text or "obe" in text:
        return "attainment_report", True
    if "自评报告" in text:
        return "self_evaluation_report", True
    if "质量报告" in text:
        return "quality_report", True
    if "学习手册" in text or "手册" in text:
        return "handbook", True
    if (
        "细则" in text
        or "机制" in text
        or "章程" in text
        or "制度" in text
        or "办法" in text
        or "督导" in text
        or "政策" in text
    ):
        return "policy", True
    if "审核评估" in text:
        return "audit_report", True
    return "other", False


def bool_label(value: bool | None) -> str:
    if value is True:
        return "yes"
    if value is False:
        return "no"
    return "need_manual_review"


def load_parser_meta(doc_root: Path, parser_name: str) -> dict[str, Any]:
    return read_json(doc_root / parser_name / "run_meta.json")


def extract_marker_features(doc_root: Path, features: DocFeatures) -> None:
    marker_json = read_json(doc_root / "marker" / "normalized.json")
    pages = marker_json.get("pages", [])
    block_type_counter: Counter[str] = Counter()
    for page in pages:
        extraction_method = str(page.get("text_extraction_method") or "").lower()
        if extraction_method == "surya":
            features.ocr_pages += 1
        elif extraction_method == "pdftext":
            features.pdftext_pages += 1

        for entry in page.get("block_counts", []):
            if not isinstance(entry, list) or len(entry) != 2:
                continue
            block_name = str(entry[0])
            try:
                count = int(entry[1])
            except Exception:
                continue
            block_type_counter[block_name] += count

    features.table_cells = block_type_counter.get("TableCell", 0)
    features.table_blocks = (
        block_type_counter.get("Table", 0)
        + block_type_counter.get("TableGroup", 0)
        + block_type_counter.get("TableOfContents", 0)
    )
    features.section_headers = block_type_counter.get("SectionHeader", 0)
    features.picture_blocks = block_type_counter.get("Picture", 0) + block_type_counter.get("Figure", 0)
    features.unique_block_types = len([k for k, v in block_type_counter.items() if v > 0])
    features.page_count = max(features.page_count, len(pages))


def extract_markdown_features(doc_root: Path, features: DocFeatures) -> None:
    md_candidates = [
        doc_root / "pymupdf4llm" / "parsed.md",
        doc_root / "marker" / "parsed.md",
        doc_root / "llamaparse" / "parsed.md",
    ]
    for md_path in md_candidates:
        content = read_text(md_path)
        if not content:
            continue
        lines = content.splitlines()
        features.pipe_table_lines = max(
            features.pipe_table_lines,
            sum(1 for line in lines if line.count("|") >= 3),
        )


def infer_table_rich(features: DocFeatures) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if features.table_cells >= 120 or features.table_blocks >= 3 or features.pipe_table_lines >= 12:
        reasons.append("marker/markdown shows dense table structure")
        return "yes", reasons
    if features.table_cells <= 5 and features.table_blocks == 0 and features.pipe_table_lines <= 1:
        reasons.append("table signals are very weak")
        return "no", reasons
    reasons.append("table signals are mixed")
    return "need_manual_review", reasons


def infer_scanned(features: DocFeatures) -> tuple[str, list[str]]:
    reasons: list[str] = []
    marker_text = max(features.marker_text_length, 1)
    pymupdf_ratio = features.pymupdf_text_length / marker_text
    if (
        features.ocr_pages >= max(1, features.page_count - 1)
        and features.pymupdf_text_length <= 100
        and features.marker_text_length >= 300
    ):
        reasons.append("OCR-dominant marker output but pymupdf text is nearly empty")
        return "yes", reasons
    if features.pymupdf_text_length >= 500 and features.pdftext_pages >= max(1, features.page_count // 2):
        reasons.append("native text extraction is available for most pages")
        return "no", reasons
    if features.ocr_pages > 0 and pymupdf_ratio < 0.25 and features.marker_text_length >= 400:
        reasons.append("OCR output is much richer than native text extraction")
        return "yes", reasons
    if features.ocr_pages == 0 and features.pdftext_pages > 0:
        reasons.append("marker relies on pdftext rather than OCR")
        return "no", reasons
    reasons.append("scan/native-text evidence is mixed")
    return "need_manual_review", reasons


def infer_structure_complex(features: DocFeatures) -> tuple[str, list[str]]:
    reasons: list[str] = []
    score = 0
    if features.page_count >= 12:
        score += 1
        reasons.append("page count is high")
    if features.unique_block_types >= 6:
        score += 1
        reasons.append("block type mix is diverse")
    if features.section_headers >= 8:
        score += 1
        reasons.append("many section headers detected")
    if features.table_rich == "yes":
        score += 1
        reasons.append("table-heavy layout")
    if features.picture_blocks >= 2:
        score += 1
        reasons.append("contains image/figure regions")
    if features.ocr_pages > 0 and features.pdftext_pages > 0:
        score += 1
        reasons.append("mixed OCR and native-text pages")

    if score >= 3:
        return "yes", reasons
    if score <= 1:
        return "no", reasons or ["layout signals are limited"]
    return "need_manual_review", reasons or ["layout signals are mixed"]


def build_doc_features(row: dict[str, str], root: Path) -> DocFeatures:
    doc_root = root / Path(row["source_pdf"]).parent
    doc_type_inferred, type_confident = normalize_doc_type(row.get("doc_type", ""), row.get("doc_dir", ""))

    features = DocFeatures(
        doc_id=row["doc_id"],
        doc_dir=row.get("doc_dir", ""),
        source_pdf=row.get("source_pdf", ""),
        doc_type_raw=row.get("doc_type", ""),
        doc_type_inferred=doc_type_inferred,
    )

    marker_meta = load_parser_meta(doc_root, "marker")
    pymupdf_meta = load_parser_meta(doc_root, "pymupdf")
    llamaparse_meta = load_parser_meta(doc_root, "llamaparse")
    features.marker_text_length = int(marker_meta.get("text_length") or 0)
    features.pymupdf_text_length = int(pymupdf_meta.get("text_length") or 0)
    features.llamaparse_text_length = int(llamaparse_meta.get("text_length") or 0)
    features.page_count = max(
        int(marker_meta.get("page_count") or 0),
        int(pymupdf_meta.get("page_count") or 0),
        int(llamaparse_meta.get("page_count") or 0),
    )

    extract_marker_features(doc_root, features)
    extract_markdown_features(doc_root, features)

    features.table_rich, table_notes = infer_table_rich(features)
    features.scanned, scan_notes = infer_scanned(features)
    features.structure_complex, complex_notes = infer_structure_complex(features)

    features.confidence_notes.extend(table_notes)
    features.confidence_notes.extend(scan_notes)
    features.confidence_notes.extend(complex_notes)

    if not type_confident:
        features.need_manual_review = True
        features.confidence_notes.append("doc_type inference is weak")
    if "need_manual_review" in {features.table_rich, features.scanned, features.structure_complex}:
        features.need_manual_review = True

    return features


def quality_score(features: DocFeatures) -> float:
    score = 0.0
    if features.table_rich == "yes":
        score += 3.0
    if features.scanned == "yes":
        score += 3.0
    if features.structure_complex == "yes":
        score += 3.0
    score += min(features.page_count, 30) / 5.0
    score += min(features.unique_block_types, 10) / 4.0
    if features.need_manual_review:
        score -= 0.5
    return score


def pick_best(candidates: list[DocFeatures]) -> DocFeatures | None:
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda x: (
            -quality_score(x),
            x.need_manual_review,
            x.doc_dir,
        ),
    )[0]


def select_subset(docs: list[DocFeatures], target_size: int) -> list[DocFeatures]:
    by_type: dict[str, list[DocFeatures]] = defaultdict(list)
    for doc in docs:
        by_type[doc.doc_type_inferred].append(doc)

    selected: list[DocFeatures] = []
    selected_ids: set[str] = set()

    for doc_type in sorted(by_type.keys()):
        candidate = pick_best(by_type[doc_type])
        if candidate and candidate.doc_id not in selected_ids:
            selected.append(candidate)
            selected_ids.add(candidate.doc_id)

    def add_by_feature(predicate: Any, quota: int) -> None:
        current = sum(1 for item in selected if predicate(item))
        if current >= quota:
            return
        candidates = [doc for doc in docs if doc.doc_id not in selected_ids and predicate(doc)]
        candidates = sorted(candidates, key=lambda x: (-quality_score(x), x.doc_dir))
        for candidate in candidates[: max(0, quota - current)]:
            selected.append(candidate)
            selected_ids.add(candidate.doc_id)

    add_by_feature(lambda x: x.scanned == "yes", min(3, sum(1 for d in docs if d.scanned == "yes")))
    add_by_feature(lambda x: x.table_rich == "yes", min(4, sum(1 for d in docs if d.table_rich == "yes")))
    add_by_feature(lambda x: x.structure_complex == "yes", min(4, sum(1 for d in docs if d.structure_complex == "yes")))
    add_by_feature(lambda x: x.table_rich == "no", min(2, sum(1 for d in docs if d.table_rich == "no")))
    add_by_feature(lambda x: x.structure_complex == "no", min(2, sum(1 for d in docs if d.structure_complex == "no")))

    remaining = [doc for doc in docs if doc.doc_id not in selected_ids]
    while len(selected) < min(target_size, len(docs)) and remaining:
        type_counts = Counter(item.doc_type_inferred for item in selected)

        def marginal_score(doc: DocFeatures) -> tuple[float, int, str]:
            score = quality_score(doc)
            score += 2.0 / (type_counts[doc.doc_type_inferred] + 1)
            if doc.table_rich == "yes" and sum(1 for x in selected if x.table_rich == "yes") < 4:
                score += 1.5
            if doc.scanned == "yes" and sum(1 for x in selected if x.scanned == "yes") < 3:
                score += 1.5
            if doc.structure_complex == "yes" and sum(1 for x in selected if x.structure_complex == "yes") < 4:
                score += 1.5
            if doc.need_manual_review:
                score -= 0.25
            return (-score, type_counts[doc.doc_type_inferred], doc.doc_dir)

        candidate = sorted(remaining, key=marginal_score)[0]
        selected.append(candidate)
        selected_ids.add(candidate.doc_id)
        remaining = [doc for doc in remaining if doc.doc_id not in selected_ids]

    for doc in selected:
        doc.selected = True
        reasons = [f"doc_type={doc.doc_type_inferred}"]
        if doc.table_rich == "yes":
            reasons.append("table_rich")
        if doc.scanned == "yes":
            reasons.append("scanned")
        if doc.structure_complex == "yes":
            reasons.append("structure_complex")
        if doc.need_manual_review:
            reasons.append("need_manual_review")
        doc.recommendation_score = round(quality_score(doc), 2)
        doc.recommendation_reason = "; ".join(reasons)

    return selected


def parse_excluded_doc_ids(raw: str) -> set[str]:
    if not raw.strip():
        return set()
    return {item.strip() for item in raw.split(",") if item.strip()}


def write_subset_csv(path: Path, subset: list[DocFeatures]) -> None:
    fieldnames = [
        "doc_id",
        "doc_dir",
        "source_pdf",
        "doc_type_raw",
        "doc_type_inferred",
        "table_rich",
        "scanned",
        "structure_complex",
        "need_manual_review",
        "page_count",
        "table_cells",
        "table_blocks",
        "section_headers",
        "unique_block_types",
        "ocr_pages",
        "pdftext_pages",
        "marker_text_length",
        "pymupdf_text_length",
        "llamaparse_text_length",
        "recommendation_score",
        "recommendation_reason",
        "confidence_notes",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for doc in subset:
            writer.writerow(
                {
                    "doc_id": doc.doc_id,
                    "doc_dir": doc.doc_dir,
                    "source_pdf": doc.source_pdf,
                    "doc_type_raw": doc.doc_type_raw,
                    "doc_type_inferred": doc.doc_type_inferred,
                    "table_rich": doc.table_rich,
                    "scanned": doc.scanned,
                    "structure_complex": doc.structure_complex,
                    "need_manual_review": str(doc.need_manual_review).lower(),
                    "page_count": doc.page_count,
                    "table_cells": doc.table_cells,
                    "table_blocks": doc.table_blocks,
                    "section_headers": doc.section_headers,
                    "unique_block_types": doc.unique_block_types,
                    "ocr_pages": doc.ocr_pages,
                    "pdftext_pages": doc.pdftext_pages,
                    "marker_text_length": doc.marker_text_length,
                    "pymupdf_text_length": doc.pymupdf_text_length,
                    "llamaparse_text_length": doc.llamaparse_text_length,
                    "recommendation_score": f"{doc.recommendation_score:.2f}",
                    "recommendation_reason": doc.recommendation_reason,
                    "confidence_notes": " | ".join(doc.confidence_notes),
                }
            )


def build_report(all_docs: list[DocFeatures], subset: list[DocFeatures], target_size: int) -> str:
    type_counter = Counter(doc.doc_type_inferred for doc in subset)
    table_count = sum(1 for doc in subset if doc.table_rich == "yes")
    scanned_count = sum(1 for doc in subset if doc.scanned == "yes")
    complex_count = sum(1 for doc in subset if doc.structure_complex == "yes")
    manual_count = sum(1 for doc in subset if doc.need_manual_review)

    lines: list[str] = []
    lines.append("# Phase 1 Parsing Subset Report")
    lines.append("")
    lines.append(f"- Candidate pool size: {len(all_docs)}")
    lines.append(f"- Recommended subset size: {len(subset)} (target={target_size})")
    lines.append(f"- Table-rich docs: {table_count}")
    lines.append(f"- Scanned docs: {scanned_count}")
    lines.append(f"- Complex-layout docs: {complex_count}")
    lines.append(f"- Need manual review: {manual_count}")
    lines.append("")
    lines.append("## Category Distribution")
    for doc_type, count in sorted(type_counter.items()):
        lines.append(f"- {doc_type}: {count}")
    lines.append("")
    lines.append("## Recommended Strategy")
    lines.append("- Cover each inferred document type at least once before filling feature-heavy slots.")
    lines.append("- Prefer documents with strong table, OCR, or complex-layout signals because they are more discriminative for parser comparison.")
    lines.append("- Keep `need_manual_review` samples in the subset when they add diversity, but mark them explicitly for later manual adjustment.")
    lines.append("")
    lines.append("## Recommended Documents")
    for doc in subset:
        lines.append(
            f"- {doc.doc_id} | {doc.doc_dir} | type={doc.doc_type_inferred} | "
            f"table={doc.table_rich} | scanned={doc.scanned} | complex={doc.structure_complex} | "
            f"manual_review={str(doc.need_manual_review).lower()} | reason={doc.recommendation_reason}"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    manifest_path = Path(args.manifest).resolve()
    output_csv = Path(args.output_csv).resolve()
    output_report = Path(args.output_report).resolve()
    parsing_eval_root = manifest_path.parent

    rows = read_csv_rows(manifest_path)
    docs = [build_doc_features(row, parsing_eval_root) for row in rows]
    excluded_doc_ids = parse_excluded_doc_ids(args.exclude_doc_ids)
    if excluded_doc_ids:
        docs = [doc for doc in docs if doc.doc_id not in excluded_doc_ids]
    subset = select_subset(docs, args.target_size)

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    write_subset_csv(output_csv, subset)
    output_report.write_text(build_report(docs, subset, args.target_size), encoding="utf-8")


if __name__ == "__main__":
    main()
