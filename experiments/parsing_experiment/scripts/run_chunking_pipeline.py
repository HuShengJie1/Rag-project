from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from chunking import chunk_document, save_chunks_csv, save_chunks_jsonl
from utils.dataset_index import load_dataset_index
from utils.logging import get_logger


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run chunking pipeline.")
    parser.add_argument("--parser", type=str, required=True, help="Parser name")
    parser.add_argument("--metadata", type=str, default=None)
    parser.add_argument("--root", type=str, default=None)
    parser.add_argument("--sheet", type=str, default=None)
    parser.add_argument("--tags", type=str, default=None)
    parser.add_argument("--strategy", type=str, default="chars", choices=["chars", "heading"])
    parser.add_argument("--chunk-size", type=int, default=800)
    parser.add_argument("--overlap", type=int, default=100)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logger = get_logger("run_chunking_pipeline")

    metadata_path = Path(args.metadata) if args.metadata else None
    root_dir = Path(args.root) if args.root else None
    index = load_dataset_index(metadata_path=metadata_path, root_dir=root_dir, sheet=args.sheet)
    if args.tags:
        tags = [t.strip() for t in args.tags.split(",") if t.strip()]
        index = index.filter_by_tags(tags)

    output_root = ROOT / "outputs" / "chunks" / args.parser / args.strategy

    for doc in index.documents:
        normalized_path = ROOT / "outputs" / "parsing" / args.parser / doc.doc_id / "normalized.json"
        if not normalized_path.exists():
            logger.info(f"skip {doc.doc_id}: normalized.json not found")
            continue
        normalized = json.loads(normalized_path.read_text(encoding="utf-8"))
        chunks = chunk_document(
            normalized,
            strategy=args.strategy,
            config={"chunk_size": args.chunk_size, "overlap": args.overlap},
        )
        out_dir = output_root / doc.doc_id
        save_chunks_jsonl(chunks, out_dir / "chunks.jsonl")
        save_chunks_csv(chunks, out_dir / "chunks.csv")
        logger.info(f"chunked {doc.doc_id}: {len(chunks)} chunks")


if __name__ == "__main__":
    main()
