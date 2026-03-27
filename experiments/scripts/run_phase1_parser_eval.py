from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = Path(__file__).resolve().parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Phase 1 parser evaluation and summary pipeline.")
    parser.add_argument("--manifest", type=str, default="experiments/parsing_eval/manifest.csv")
    parser.add_argument("--subset", type=str, default="experiments/parsing_eval/phase1_subset.csv")
    parser.add_argument("--gt-manifest", type=str, default="experiments/parsing_eval/ground_truth/gt_manifest.csv")
    parser.add_argument("--output-dir", type=str, default="experiments/outputs/parsing_eval")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    python_exe = sys.executable

    eval_cmd = [
        python_exe,
        str(SCRIPT_DIR / "parser_eval.py"),
        "--manifest",
        args.manifest,
        "--subset",
        args.subset,
        "--gt-manifest",
        args.gt_manifest,
        "--output-dir",
        args.output_dir,
    ]
    summarize_cmd = [
        python_exe,
        str(SCRIPT_DIR / "summarize_parser_eval.py"),
        "--results",
        f"{args.output_dir}/parser_results.csv",
        "--subset",
        args.subset,
        "--manifest",
        args.manifest,
        "--output-dir",
        args.output_dir,
    ]

    subprocess.run(eval_cmd, check=True, cwd=REPO_ROOT)
    subprocess.run(summarize_cmd, check=True, cwd=REPO_ROOT)


if __name__ == "__main__":
    main()
