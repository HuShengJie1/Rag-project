from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import os
import shutil
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from utils.io import ensure_dir, write_csv, write_text
from utils.logging import get_logger


PARSER_NAMES = ["marker", "pymupdf", "pymupdf4llm", "pdfplumber", "unstructured", "llamaparse"]
PARSER_FIELDS = {
    "marker": "marker_output",
    "pymupdf": "pymupdf_output",
    "pymupdf4llm": "pymupdf4llm_output",
    "pdfplumber": "pdfplumber_output",
    "unstructured": "unstructured_output",
    "llamaparse": "llamaparse_output",
}


@dataclass
class SourceMeta:
    doc_id: str
    source_pdf: Path | None = None
    source_url: str = ""
    doc_type: str = ""
    university_name: str = ""
    document_title: str = ""
    file_type: str = ""
    tags: str = ""


@dataclass
class ParserRecord:
    parser_name: str
    source_dir: Path
    files: list[Path] = field(default_factory=list)
    run_meta: dict[str, Any] = field(default_factory=dict)
    success: bool | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Organize parsing outputs for parser evaluation.")
    parser.add_argument("--parsing-root", type=str, default="experiments/outputs/parsing")
    parser.add_argument("--downloads-root", type=str, default="experiments/outputs/downloads")
    parser.add_argument("--dataset-index", type=str, default="experiments/outputs/dataset_index.csv")
    parser.add_argument("--output-root", type=str, default="experiments/parsing_eval")
    parser.add_argument("--copy-mode", type=str, choices=["copy", "hardlink"], default="copy")
    return parser.parse_args()


def read_dataset_index(path: Path) -> dict[str, SourceMeta]:
    if not path.exists():
        return {}

    result: dict[str, SourceMeta] = {}
    with path.open("r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            doc_id = (row.get("doc_id") or "").strip()
            if not doc_id:
                continue

            metadata_text = row.get("metadata", "") or ""
            metadata: dict[str, Any] = {}
            if metadata_text:
                try:
                    metadata = ast.literal_eval(metadata_text)
                except Exception:
                    metadata = {}

            file_path = (row.get("file_path") or "").strip()
            source_pdf = Path(file_path) if file_path else None
            result[doc_id] = SourceMeta(
                doc_id=doc_id,
                source_pdf=source_pdf,
                source_url=(row.get("source_url") or "").strip(),
                doc_type=str(
                    metadata.get("document_type")
                    or metadata.get("doc_type")
                    or row.get("file_type")
                    or ""
                ).strip(),
                university_name=str(metadata.get("university_name") or "").strip(),
                document_title=str(metadata.get("document_title") or "").strip(),
                file_type=(row.get("file_type") or "").strip(),
                tags=(row.get("tags") or "").strip(),
            )
    return result


def infer_doc_type(meta: SourceMeta, doc_id: str) -> str:
    if meta.doc_type:
        return meta.doc_type
    text = " ".join([meta.document_title, meta.tags, meta.file_type, doc_id]).lower()
    if "大纲" in text or "syllabus" in text:
        return "syllabus"
    if "达成" in text or "attainment" in text:
        return "attainment_report"
    if "课程体系" in text:
        return "curriculum_eval"
    if "评价细则" in text:
        return "evaluation_rules"
    return ""


def resolve_source_pdf(doc_id: str, downloads_root: Path, meta: SourceMeta | None) -> Path | None:
    if meta and meta.source_pdf and meta.source_pdf.exists():
        return meta.source_pdf

    candidates = sorted(downloads_root.glob(f"{doc_id}.*"))
    for candidate in candidates:
        if candidate.is_file() and candidate.suffix.lower() == ".pdf":
            return candidate

    if meta and meta.source_url:
        suffix = Path(meta.source_url).suffix.lower()
        if suffix == ".pdf":
            candidate = downloads_root / f"{doc_id}.pdf"
            if candidate.exists():
                return candidate
    return None


def sanitize_dir_name(name: str) -> str:
    invalid_chars = '<>:"/\\|?*'
    sanitized = []
    for char in name.strip():
        sanitized.append("_" if char in invalid_chars else char)
    value = "".join(sanitized).strip().rstrip(". ")
    return value or "untitled"


def build_doc_dir_names(doc_ids: list[str], source_meta_map: dict[str, SourceMeta]) -> dict[str, str]:
    used: dict[str, int] = {}
    mapping: dict[str, str] = {}
    for doc_id in doc_ids:
        meta = source_meta_map.get(doc_id, SourceMeta(doc_id=doc_id))
        base = " ".join(part for part in [meta.university_name, meta.document_title] if part).strip()
        if not base:
            base = doc_id
        candidate = sanitize_dir_name(base)
        count = used.get(candidate, 0)
        final_name = candidate if count == 0 else f"{candidate} [{doc_id}]"
        used[candidate] = count + 1
        mapping[doc_id] = final_name
    return mapping


def scan_parser_outputs(parsing_root: Path) -> dict[str, dict[str, ParserRecord]]:
    records: dict[str, dict[str, ParserRecord]] = defaultdict(dict)
    if not parsing_root.exists():
        return records

    for parser_dir in sorted(parsing_root.iterdir()):
        if not parser_dir.is_dir():
            continue
        parser_name = parser_dir.name
        if parser_name not in PARSER_NAMES:
            continue

        for doc_dir in sorted(parser_dir.iterdir()):
            if not doc_dir.is_dir():
                continue
            doc_id = doc_dir.name
            files = sorted([p for p in doc_dir.iterdir() if p.is_file()])
            run_meta_path = doc_dir / "run_meta.json"
            run_meta: dict[str, Any] = {}
            success: bool | None = None
            if run_meta_path.exists():
                try:
                    run_meta = json.loads(run_meta_path.read_text(encoding="utf-8"))
                    raw_success = run_meta.get("success")
                    if isinstance(raw_success, bool):
                        success = raw_success
                    elif isinstance(raw_success, str):
                        success = raw_success.lower() == "true"
                except Exception:
                    run_meta = {}
            records[doc_id][parser_name] = ParserRecord(
                parser_name=parser_name,
                source_dir=doc_dir,
                files=files,
                run_meta=run_meta,
                success=success,
            )
    return records


def copy_file(src: Path, dst: Path, copy_mode: str) -> None:
    ensure_dir(dst.parent)
    if dst.exists():
        if dst.stat().st_size == src.stat().st_size:
            return
        try:
            dst.chmod(0o666)
            dst.unlink()
        except PermissionError:
            return
    if copy_mode == "hardlink":
        try:
            dst.hardlink_to(src)
            return
        except Exception:
            pass
    shutil.copy2(src, dst)


def remove_tree(path: Path) -> None:
    def _onerror(func: Any, target: str, _exc_info: Any) -> None:
        os.chmod(target, 0o666)
        func(target)

    shutil.rmtree(path, onerror=_onerror)


def copy_parser_record(target_doc_dir: Path, record: ParserRecord, copy_mode: str) -> Path | None:
    if not record.files:
        return None

    target_dir = ensure_dir(target_doc_dir / record.parser_name)
    for file_path in record.files:
        copy_file(file_path, target_dir / file_path.name, copy_mode)
    return target_dir


def has_content_files(record: ParserRecord) -> bool:
    for file_path in record.files:
        if file_path.name in {"raw.txt", "parsed.md", "normalized.json"} and file_path.stat().st_size > 0:
            return True
    return False


def is_usable_output(record: ParserRecord) -> bool:
    if record.success is False:
        return False
    return has_content_files(record)


def file_sha1(path: Path) -> str:
    h = hashlib.sha1()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def build_summary(
    total_docs: int,
    manifest_rows: list[dict[str, str]],
    parser_coverage: dict[str, int],
    duplicate_lines: list[str],
) -> str:
    lines: list[str] = []
    lines.append("# Parsing Eval Summary")
    lines.append("")
    lines.append(f"- Total documents: {total_docs}")
    for parser_name in PARSER_NAMES:
        lines.append(f"- {parser_name} coverage: {parser_coverage.get(parser_name, 0)}")

    lines.append("")
    lines.append("## Missing Outputs")
    missing_counts = {parser_name: 0 for parser_name in PARSER_NAMES}
    for row in manifest_rows:
        for parser_name, field in PARSER_FIELDS.items():
            if not row.get(field):
                missing_counts[parser_name] += 1
    for parser_name in PARSER_NAMES:
        lines.append(f"- {parser_name}: missing for {missing_counts[parser_name]} docs")

    lines.append("")
    lines.append("## Missing Details")
    missing_detail_count = 0
    for row in manifest_rows:
        missing = [parser for parser, field in PARSER_FIELDS.items() if not row.get(field)]
        if missing:
            missing_detail_count += 1
            lines.append(f"- {row['doc_id']}: {', '.join(missing)}")
    if missing_detail_count == 0:
        lines.append("- None")

    lines.append("")
    lines.append("## Duplicate Suspects")
    if duplicate_lines:
        lines.extend(f"- {line}" for line in duplicate_lines)
    else:
        lines.append("- None")

    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    parsing_root = Path(args.parsing_root).resolve()
    downloads_root = Path(args.downloads_root).resolve()
    dataset_index_path = Path(args.dataset_index).resolve()
    output_root = Path(args.output_root).resolve()
    docs_root = ensure_dir(output_root / "docs")
    logger = get_logger("organize_parsing_results", ROOT / "outputs" / "logs" / "organize_parsing_results.log")

    source_meta_map = read_dataset_index(dataset_index_path)
    parser_records = scan_parser_outputs(parsing_root)

    all_doc_ids = sorted(set(source_meta_map.keys()) | set(parser_records.keys()), key=lambda x: (len(x), x))
    doc_dir_names = build_doc_dir_names(all_doc_ids, source_meta_map)
    manifest_rows: list[dict[str, str]] = []
    parser_coverage = {parser_name: 0 for parser_name in PARSER_NAMES}
    duplicate_keys: dict[str, list[str]] = defaultdict(list)
    title_keys: dict[str, list[str]] = defaultdict(list)

    for doc_id in all_doc_ids:
        meta = source_meta_map.get(doc_id, SourceMeta(doc_id=doc_id))
        target_doc_dir = docs_root / doc_dir_names[doc_id]
        legacy_doc_dir = docs_root / doc_id
        if not target_doc_dir.exists() and legacy_doc_dir.exists() and legacy_doc_dir != target_doc_dir:
            try:
                legacy_doc_dir.rename(target_doc_dir)
            except PermissionError:
                logger.warning("Rename failed for doc_id=%s, fallback to copy into %s", doc_id, target_doc_dir.name)
        target_doc_dir = ensure_dir(target_doc_dir)
        source_pdf = resolve_source_pdf(doc_id, downloads_root, meta)
        source_pdf_rel = ""
        if source_pdf and source_pdf.exists():
            target_pdf = target_doc_dir / "source.pdf"
            copy_file(source_pdf, target_pdf, args.copy_mode)
            source_pdf_rel = str(target_pdf.relative_to(output_root))
            try:
                duplicate_keys[file_sha1(source_pdf)].append(doc_id)
            except Exception:
                logger.warning("Failed to hash source pdf for doc_id=%s", doc_id)

        title_key = meta.document_title.strip().lower()
        if title_key:
            title_keys[title_key].append(doc_id)

        row = {
            "doc_id": doc_id,
            "doc_dir": doc_dir_names[doc_id],
            "source_pdf": source_pdf_rel,
            "marker_output": "",
            "marker_status": "missing",
            "marker_error": "",
            "pymupdf_output": "",
            "pymupdf_status": "missing",
            "pymupdf_error": "",
            "pymupdf4llm_output": "",
            "pymupdf4llm_status": "missing",
            "pymupdf4llm_error": "",
            "pdfplumber_output": "",
            "pdfplumber_status": "missing",
            "pdfplumber_error": "",
            "unstructured_output": "",
            "unstructured_status": "missing",
            "unstructured_error": "",
            "llamaparse_output": "",
            "llamaparse_status": "missing",
            "llamaparse_error": "",
            "doc_type": infer_doc_type(meta, doc_id),
        }

        for parser_name in PARSER_NAMES:
            record = parser_records.get(doc_id, {}).get(parser_name)
            if record is None:
                continue
            target_dir = copy_parser_record(target_doc_dir, record, args.copy_mode)
            row[f"{parser_name}_status"] = (
                "success" if record.success is True else "failed" if record.success is False else "unknown"
            )
            row[f"{parser_name}_error"] = str(record.run_meta.get("error_message") or "")
            if target_dir is not None and is_usable_output(record):
                row[PARSER_FIELDS[parser_name]] = str(target_dir.relative_to(output_root))
                parser_coverage[parser_name] += 1

        manifest_rows.append(row)

    fieldnames = [
        "doc_id",
        "doc_dir",
        "source_pdf",
        "marker_output",
        "marker_status",
        "marker_error",
        "pymupdf_output",
        "pymupdf_status",
        "pymupdf_error",
        "pymupdf4llm_output",
        "pymupdf4llm_status",
        "pymupdf4llm_error",
        "pdfplumber_output",
        "pdfplumber_status",
        "pdfplumber_error",
        "unstructured_output",
        "unstructured_status",
        "unstructured_error",
        "llamaparse_output",
        "llamaparse_status",
        "llamaparse_error",
        "doc_type",
    ]
    write_csv(output_root / "manifest.csv", manifest_rows, fieldnames)

    duplicate_lines: list[str] = []
    for sha1, doc_ids in sorted(duplicate_keys.items()):
        if len(doc_ids) > 1:
            duplicate_lines.append(f"same_source_pdf_sha1={sha1} -> {', '.join(sorted(doc_ids, key=lambda x: (len(x), x)))}")
    for title, doc_ids in sorted(title_keys.items()):
        if len(doc_ids) > 1:
            duplicate_lines.append(f"same_document_title={title} -> {', '.join(sorted(doc_ids, key=lambda x: (len(x), x)))}")

    summary = build_summary(
        total_docs=len(manifest_rows),
        manifest_rows=manifest_rows,
        parser_coverage=parser_coverage,
        duplicate_lines=duplicate_lines,
    )
    write_text(output_root / "summary.md", summary)

    removed_legacy_dirs = 0
    for doc_id, doc_dir_name in doc_dir_names.items():
        legacy_doc_dir = docs_root / doc_id
        named_doc_dir = docs_root / doc_dir_name
        if legacy_doc_dir.exists() and legacy_doc_dir.is_dir() and named_doc_dir.exists() and named_doc_dir.is_dir():
            try:
                remove_tree(legacy_doc_dir)
                removed_legacy_dirs += 1
            except Exception as exc:
                logger.warning("Failed to remove legacy doc dir for doc_id=%s: %s", doc_id, exc)

    if removed_legacy_dirs:
        logger.info("Removed %s legacy numeric doc dirs", removed_legacy_dirs)
    logger.info("Organized %s docs into %s", len(manifest_rows), output_root)


if __name__ == "__main__":
    main()
