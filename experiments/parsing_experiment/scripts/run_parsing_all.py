from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run parsing experiments for all parsers.")
    parser.add_argument("--metadata", type=str, default=None)
    parser.add_argument("--root", type=str, default=None)
    parser.add_argument("--sheet", type=str, default=None)
    parser.add_argument("--tags", type=str, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--config", type=str, default=None)
    parser.add_argument("--column-map", type=str, default=None)
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--download-dir", type=str, default="outputs/downloads")
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--no-auto-ocr", action="store_true")
    parser.add_argument("--ocr-parser", type=str, default="ocr_tesseract")
    parser.add_argument("--ocr-lang", type=str, default="chi_sim+eng")
    parser.add_argument("--ocr-dpi", type=int, default=200)
    parser.add_argument("--tesseract-cmd", type=str, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    parsers = ["pymupdf", "pymupdf4llm", "pdfplumber", "unstructured", "marker", "llamaparse"]

    base_cmd = [sys.executable, str(ROOT / "scripts" / "run_parsing_experiment.py")]

    for parser_name in parsers:
        cmd = base_cmd + ["--parser", parser_name, "--append"]
        if args.metadata:
            cmd += ["--metadata", args.metadata]
        if args.root:
            cmd += ["--root", args.root]
        if args.sheet:
            cmd += ["--sheet", args.sheet]
        if args.tags:
            cmd += ["--tags", args.tags]
        if args.limit is not None:
            cmd += ["--limit", str(args.limit)]
        if args.config:
            cmd += ["--config", args.config]
        if args.column_map:
            cmd += ["--column-map", args.column_map]
        if args.download:
            cmd += ["--download", "--download-dir", args.download_dir, "--timeout", str(args.timeout)]
        if args.no_auto_ocr:
            cmd += ["--no-auto-ocr"]
        if args.ocr_parser:
            cmd += ["--ocr-parser", args.ocr_parser]
        if args.ocr_lang:
            cmd += ["--ocr-lang", args.ocr_lang]
        if args.ocr_dpi:
            cmd += ["--ocr-dpi", str(args.ocr_dpi)]
        if args.tesseract_cmd:
            cmd += ["--tesseract-cmd", args.tesseract_cmd]

        print(f"[run] {parser_name}")
        try:
            subprocess.run(cmd, check=False)
        except KeyboardInterrupt:
            print("Interrupted.")
            break


if __name__ == "__main__":
    main()
