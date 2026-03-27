from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from parsers import PARSER_REGISTRY
from normalize import normalize_parse_result
from utils.dataset_index import load_dataset_index
from utils.downloader import download_file
from utils.io import ensure_dir, write_json, write_text
from utils.logging import get_logger


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run parsing experiments.")
    parser.add_argument("--parser", type=str, required=True, help="Parser name")
    parser.add_argument("--metadata", type=str, default=None)
    parser.add_argument("--root", type=str, default=None)
    parser.add_argument("--sheet", type=str, default=None)
    parser.add_argument("--tags", type=str, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--config", type=str, default=None, help="Parser config file (json/yaml)")
    parser.add_argument("--column-map", type=str, default=None, help="JSON mapping for columns")
    parser.add_argument("--download", action="store_true", help="Download files from URL if local path missing")
    parser.add_argument("--download-dir", type=str, default="outputs/downloads", help="Download directory")
    parser.add_argument("--timeout", type=int, default=60, help="Download timeout in seconds")
    parser.add_argument("--no-auto-ocr", action="store_true", help="Disable auto OCR for scanned_ocr tags")
    parser.add_argument("--ocr-parser", type=str, default="ocr_tesseract", help="OCR parser name")
    parser.add_argument("--ocr-lang", type=str, default="chi_sim+eng")
    parser.add_argument("--ocr-dpi", type=int, default=200)
    parser.add_argument("--tesseract-cmd", type=str, default=None)
    parser.add_argument("--append", action="store_true", help="Append to existing results CSV")
    return parser.parse_args()


def load_config(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")
    if config_path.suffix.lower() in [".yaml", ".yml"]:
        try:
            import yaml
        except Exception as e:
            raise ImportError("缺少 PyYAML 依赖，请安装：pip install pyyaml") from e
        return yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    return json.loads(config_path.read_text(encoding="utf-8"))


def read_existing_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def write_results_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    ensure_dir(path.parent)
    fieldnames: list[str] = []
    for r in rows:
        for k in r.keys():
            if k not in fieldnames:
                fieldnames.append(k)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    logger = get_logger("run_parsing_experiment", ROOT / "outputs" / "logs" / f"parsing_{args.parser}_{int(time.time())}.log")

    parser_name = args.parser.lower()
    if parser_name not in PARSER_REGISTRY:
        raise ValueError(f"Unknown parser: {parser_name}")

    metadata_path = Path(args.metadata) if args.metadata else None
    root_dir = Path(args.root) if args.root else None
    config = load_config(args.config)

    column_map = json.loads(args.column_map) if args.column_map else None
    download_dir = ROOT / args.download_dir
    index = load_dataset_index(
        metadata_path=metadata_path,
        root_dir=root_dir,
        sheet=args.sheet,
        column_map=column_map,
        # Always map URL-only records to the local download directory first.
        # If files already exist there, users can run without --download.
        default_download_dir=download_dir,
    )
    if args.tags:
        tags = [t.strip() for t in args.tags.split(",") if t.strip()]
        index = index.filter_by_tags(tags)

    documents = index.documents
    if args.limit:
        documents = documents[: args.limit]

    parser_cls = PARSER_REGISTRY[parser_name]
    parser = parser_cls()
    auto_ocr = not args.no_auto_ocr
    ocr_parser_name = args.ocr_parser.lower()
    ocr_parser = None
    if ocr_parser_name in PARSER_REGISTRY:
        ocr_parser = PARSER_REGISTRY[ocr_parser_name]()

    output_root = ROOT / "outputs" / "parsing" / parser_name
    results_rows: list[dict[str, Any]] = []

    for doc in documents:
        logger.info(f"Parsing {doc.doc_id} | {doc.file_path}")
        out_dir = output_root / doc.doc_id
        ensure_dir(out_dir)

        if not doc.valid and args.download and doc.source_url:
            try:
                downloaded = download_file(
                    doc.source_url,
                    download_dir,
                    name_hint=doc.doc_id,
                    timeout=args.timeout,
                )
                doc.file_path = downloaded
                doc.valid = True
                doc.errors = []
            except Exception as e:
                doc.errors.append(f"download failed: {e}")

        if not doc.valid:
            result = {
                "doc_id": doc.doc_id,
                "parser_name": parser_name,
                "success": False,
                "elapsed_time": 0.0,
                "text_length": 0,
                "markdown_length": 0,
                "page_count": 0,
                "error_message": "; ".join(doc.errors),
            }
            write_json(out_dir / "run_meta.json", result)
            results_rows.append(result)
            continue

        actual_parser = parser
        actual_parser_name = parser_name
        if auto_ocr and any(t.lower() == "scanned_ocr" for t in doc.tags):
            if ocr_parser is None:
                parse_result = parser.parse(doc.file_path, config=config)
                parse_result.success = False
                parse_result.error_message = "OCR parser not available"
            else:
                actual_parser = ocr_parser
                actual_parser_name = ocr_parser_name
                ocr_config = {
                    "lang": args.ocr_lang,
                    "dpi": args.ocr_dpi,
                    "tesseract_cmd": args.tesseract_cmd,
                }
                parse_result = actual_parser.parse(doc.file_path, config=ocr_config)
        else:
            parse_result = actual_parser.parse(doc.file_path, config=config)
        parse_result.parser_name = actual_parser_name
        normalized = normalize_parse_result(doc.doc_id, doc.file_path, parse_result)

        raw_text = parse_result.raw_text or ""
        markdown = parse_result.markdown or ""
        write_text(out_dir / "raw.txt", raw_text)
        if markdown:
            write_text(out_dir / "parsed.md", markdown)
        write_json(out_dir / "normalized.json", normalized)

        meta = {
            "doc_id": doc.doc_id,
            "parser_name": parser_name,
            "actual_parser": actual_parser_name,
            "success": parse_result.success,
            "elapsed_time": round(parse_result.elapsed_time, 4),
            "text_length": len(raw_text),
            "markdown_length": len(markdown),
            "page_count": len(parse_result.page_metadata) if parse_result.page_metadata else 0,
            "error_message": parse_result.error_message or "",
        }
        write_json(out_dir / "run_meta.json", meta)
        results_rows.append(meta)

    results_path = ROOT / "outputs" / "parsing" / "parsing_results.csv"
    if args.append and results_path.exists():
        existing = read_existing_csv(results_path)
        results_rows = existing + results_rows

    write_results_csv(results_path, results_rows)

    success_count = len([r for r in results_rows if str(r.get("success")).lower() == "true"])
    logger.info(f"Run completed: total={len(results_rows)}, success={success_count}")


if __name__ == "__main__":
    main()
