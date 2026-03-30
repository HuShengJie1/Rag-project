#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from chunkers.chunking import chunk_markdown_file
from loaders.mineru_loader import load_pdf


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )


def ensure_markdown_for_pdf(pdf_path: Path, md_dir: Path, force_mineru: bool = False) -> tuple[Path, bool]:
    md_path = md_dir / f"{pdf_path.stem}.md"
    if md_path.exists() and not force_mineru:
        return md_path, False

    if force_mineru:
        logging.info("Force re-parse with MinerU(local): %s", pdf_path.name)
    else:
        logging.info("Markdown missing for %s, parsing with MinerU(local)...", pdf_path.name)
    records = load_pdf(str(pdf_path))
    content = "\n\n\n".join(str(rec.get("text", "")) for rec in records)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(content, encoding="utf-8")
    return md_path, True


def pick_page(meta: dict[str, Any]) -> int | None:
    page_labels = meta.get("page_labels")
    if isinstance(page_labels, list) and page_labels:
        try:
            return int(page_labels[0])
        except Exception:
            return None
    if isinstance(page_labels, (int, float)):
        return int(page_labels)
    if isinstance(page_labels, str) and page_labels.strip().isdigit():
        return int(page_labels.strip())
    return None


def build_embedding_text(text: str, doc_name: str, headers: list[str] | None) -> str:
    header_values = [str(h).strip() for h in (headers or []) if str(h).strip()]
    header_line = " > ".join(header_values)
    parts = [f"【来源文档】{doc_name}"]
    if header_line:
        parts.append(f"【标题层级】{header_line}")
    parts.append(str(text).strip())
    return "\n".join(parts).strip()


def build_corpus(
    pdf_dir: Path,
    md_dir: Path,
    *,
    chunk_size: int = 800,
    chunk_overlap: int = 120,
    force_mineru: bool = False,
) -> tuple[list[dict[str, Any]], list[str], int]:
    pdf_files = sorted(pdf_dir.glob("*.pdf"))
    if not pdf_files:
        raise FileNotFoundError(f"No pdf found in {pdf_dir}")

    corpus_chunks: list[dict[str, Any]] = []
    failed_docs: list[str] = []
    generated_md_count = 0

    for pdf_path in pdf_files:
        try:
            md_path, generated = ensure_markdown_for_pdf(
                pdf_path,
                md_dir,
                force_mineru=force_mineru,
            )
            if generated:
                generated_md_count += 1

            chunks = chunk_markdown_file(
                path=md_path,
                file_id=pdf_path.name,
                user_id="system",
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
            if not chunks:
                logging.warning("No chunks generated for %s", pdf_path.name)
                failed_docs.append(pdf_path.name)
                continue

            for ch in chunks:
                meta = ch.get("metadata", {})
                if not isinstance(meta, dict):
                    meta = {}

                corpus_chunks.append(
                    {
                        "chunk_id": ch.get("chunk_id"),
                        "text": ch.get("text", ""),
                        "embedding_text": build_embedding_text(
                            text=ch.get("text", ""),
                            doc_name=pdf_path.name,
                            headers=meta.get("headers", []),
                        ),
                        "file_path": str(pdf_path.resolve()),
                        "page": pick_page(meta),
                        "metadata": {
                            "source_pdf": str(pdf_path.resolve()),
                            "source_md": str(md_path.resolve()),
                            "doc_name": pdf_path.name,
                            "header_hierarchy": meta.get("headers", []),
                            "section_title": (meta.get("headers") or [None])[-1],
                            "page_labels": meta.get("page_labels", []),
                            "chunk_seq": meta.get("chunk_seq"),
                            "original_doc_id": pdf_path.stem,
                        },
                    }
                )
        except Exception as exc:  # pragma: no cover
            logging.exception("Failed to process %s: %s", pdf_path.name, exc)
            failed_docs.append(pdf_path.name)

    return corpus_chunks, failed_docs, generated_md_count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build end2end corpus chunks from data/system_docs")
    parser.add_argument(
        "--pdf-dir",
        type=str,
        default=str(PROJECT_ROOT / "data" / "system_docs"),
    )
    parser.add_argument(
        "--md-dir",
        type=str,
        default=str(PROJECT_ROOT / "data" / "parsed" / "md"),
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(PROJECT_ROOT / "experiments" / "end2end" / "data" / "corpus_chunks.json"),
    )
    parser.add_argument(
        "--force-mineru",
        action="store_true",
        help="Re-parse all PDFs with MinerU and overwrite existing markdown files.",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=800,
        help="Recursive splitter chunk size.",
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=120,
        help="Recursive splitter chunk overlap.",
    )
    return parser.parse_args()


def main() -> None:
    setup_logging()
    args = parse_args()

    pdf_dir = Path(args.pdf_dir)
    md_dir = Path(args.md_dir)
    output_path = Path(args.output)

    corpus, failed_docs, generated_md_count = build_corpus(
        pdf_dir,
        md_dir,
        chunk_size=int(args.chunk_size),
        chunk_overlap=int(args.chunk_overlap),
        force_mineru=args.force_mineru,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(corpus, ensure_ascii=False, indent=2), encoding="utf-8")

    logging.info("Done. corpus_chunks=%d", len(corpus))
    logging.info("Chunk params: size=%d overlap=%d", int(args.chunk_size), int(args.chunk_overlap))
    logging.info("Output: %s", output_path)
    logging.info("Generated missing markdown files: %d", generated_md_count)
    if failed_docs:
        logging.warning("Failed documents (%d): %s", len(failed_docs), ", ".join(failed_docs))
    else:
        logging.info("All PDFs processed successfully.")


if __name__ == "__main__":
    main()
