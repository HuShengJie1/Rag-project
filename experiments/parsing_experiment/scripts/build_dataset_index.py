from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from utils.dataset_index import load_dataset_index
from utils.io import write_jsonl, write_csv
from utils.logging import get_logger


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build dataset index from metadata Excel.")
    parser.add_argument("--metadata", type=str, default=None, help="Path to metadata xlsx")
    parser.add_argument("--root", type=str, default=None, help="Root dir for relative paths")
    parser.add_argument("--sheet", type=str, default=None, help="Sheet name")
    parser.add_argument("--tags", type=str, default=None, help="Comma-separated tags filter")
    parser.add_argument("--only-valid", action="store_true", help="Only keep valid documents")
    parser.add_argument("--column-map", type=str, default=None, help="JSON mapping for columns")
    parser.add_argument("--out-jsonl", type=str, default="outputs/dataset_index.jsonl")
    parser.add_argument("--out-csv", type=str, default="outputs/dataset_index.csv")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logger = get_logger("build_dataset_index")

    metadata_path = Path(args.metadata) if args.metadata else None
    root_dir = Path(args.root) if args.root else None

    column_map = json.loads(args.column_map) if args.column_map else None
    index = load_dataset_index(metadata_path=metadata_path, root_dir=root_dir, sheet=args.sheet, column_map=column_map)
    if args.tags:
        tags = [t.strip() for t in args.tags.split(",") if t.strip()]
        index = index.filter_by_tags(tags)

    documents = index.documents
    if args.only_valid:
        documents = [d for d in documents if d.valid]

    rows = [d.to_record() for d in documents]
    out_jsonl = ROOT / args.out_jsonl
    out_csv = ROOT / args.out_csv

    write_jsonl(out_jsonl, rows)
    write_csv(out_csv, rows, fieldnames=list(rows[0].keys()) if rows else [])

    total = len(index.documents)
    valid = len([d for d in index.documents if d.valid])
    logger.info(f"Index built: total={total}, valid={valid}, output={out_jsonl}")


if __name__ == "__main__":
    main()
