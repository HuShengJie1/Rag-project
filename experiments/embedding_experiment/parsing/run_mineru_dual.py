from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path

from manifest import MANIFEST_FIELDS


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run MinerU twice (pipeline + vlm/auto) and keep outputs/manifests separated."
    )
    parser.add_argument("--input_dir", required=True, type=Path, help="Input documents directory.")
    parser.add_argument("--output_root", required=True, type=Path, help="Root output directory for dual runs.")
    parser.add_argument("--manifest_root", required=True, type=Path, help="Directory for manifest outputs.")
    parser.add_argument("--mineru_bin", default=".venv/bin/mineru", help="MinerU CLI executable path.")
    parser.add_argument("--hf_cache_dir", type=Path, default=None, help="HF cache dir (typically .../hub).")
    parser.add_argument("--retries", type=int, default=1, help="Retry count for failed files.")
    parser.add_argument("--timeout_sec", type=int, default=None, help="Per-file timeout in seconds.")
    parser.add_argument("--include_docx", action="store_true", help="Include DOCX files.")
    parser.add_argument("--include_images", action="store_true", help="Include image files.")
    parser.add_argument("--dry_run", action="store_true", help="Dry-run for both profiles.")
    parser.add_argument(
        "--skip-existing",
        "--skip_existing",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Skip files whose output directory already has content.",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logs in child runs.")
    parser.add_argument("--python_bin", default=sys.executable, help="Python executable for invoking child runs.")
    return parser.parse_args()


def _to_abs(path: Path) -> Path:
    return path.expanduser().resolve()


def _profile_paths(manifest_root: Path, output_root: Path, profile: str) -> dict[str, Path]:
    return {
        "output_dir": output_root / profile,
        "manifest_csv": manifest_root / f"manifest.{profile}.csv",
        "manifest_json": manifest_root / f"manifest.{profile}.json",
    }


def _build_child_command(
    *,
    python_bin: str,
    batch_script: Path,
    input_dir: Path,
    output_dir: Path,
    manifest_csv: Path,
    manifest_json: Path,
    profile: str,
    backend: str,
    mineru_bin: str,
    hf_cache_dir: Path | None,
    retries: int,
    timeout_sec: int | None,
    include_docx: bool,
    include_images: bool,
    dry_run: bool,
    skip_existing: bool,
    verbose: bool,
) -> list[str]:
    cmd = [
        python_bin,
        str(batch_script),
        "--input_dir",
        str(input_dir),
        "--output_dir",
        str(output_dir),
        "--manifest",
        str(manifest_csv),
        "--manifest_json",
        str(manifest_json),
        "--backend",
        backend,
        "--run_profile",
        profile,
        "--retries",
        str(retries),
        "--mineru_bin",
        mineru_bin,
    ]
    if hf_cache_dir is not None:
        cmd.extend(["--hf_cache_dir", str(hf_cache_dir)])
    if timeout_sec is not None:
        cmd.extend(["--timeout_sec", str(timeout_sec)])
    if include_docx:
        cmd.append("--include_docx")
    if include_images:
        cmd.append("--include_images")
    if dry_run:
        cmd.append("--dry_run")
    cmd.append("--skip-existing" if skip_existing else "--no-skip-existing")
    if verbose:
        cmd.append("--verbose")
    return cmd


def _read_manifest_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _write_combined_csv(rows: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        for row in rows:
            normalized = {field: row.get(field, "") for field in MANIFEST_FIELDS}
            writer.writerow(normalized)


def _write_combined_json(rows: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def _summarize(rows: list[dict]) -> dict[str, int]:
    result = {"total": len(rows), "success": 0, "failed": 0, "skipped": 0, "with_md": 0}
    for row in rows:
        status = row.get("parse_status")
        if status in result:
            result[status] += 1
        if row.get("output_md_exists"):
            result["with_md"] += 1
    return result


def main() -> int:
    args = parse_args()
    input_dir = _to_abs(args.input_dir)
    output_root = _to_abs(args.output_root)
    manifest_root = _to_abs(args.manifest_root)

    output_root.mkdir(parents=True, exist_ok=True)
    manifest_root.mkdir(parents=True, exist_ok=True)

    batch_script = Path(__file__).with_name("run_mineru_batch.py").resolve()

    profiles = [
        ("pipeline", "pipeline"),
        ("vlm", "auto"),
    ]

    exit_codes: dict[str, int] = {}
    profile_rows: dict[str, list[dict]] = {}

    for profile, backend in profiles:
        paths = _profile_paths(manifest_root, output_root, profile)
        cmd = _build_child_command(
            python_bin=args.python_bin,
            batch_script=batch_script,
            input_dir=input_dir,
            output_dir=paths["output_dir"],
            manifest_csv=paths["manifest_csv"],
            manifest_json=paths["manifest_json"],
            profile=profile,
            backend=backend,
            mineru_bin=args.mineru_bin,
            hf_cache_dir=_to_abs(args.hf_cache_dir) if args.hf_cache_dir else None,
            retries=max(0, args.retries),
            timeout_sec=args.timeout_sec,
            include_docx=args.include_docx,
            include_images=args.include_images,
            dry_run=args.dry_run,
            skip_existing=args.skip_existing,
            verbose=args.verbose,
        )

        print(f"\n=== Running profile: {profile} (backend={backend}) ===")
        print("Command:", " ".join(cmd))
        completed = subprocess.run(cmd, check=False)
        exit_codes[profile] = completed.returncode
        profile_rows[profile] = _read_manifest_rows(paths["manifest_json"])

    combined_rows = profile_rows.get("pipeline", []) + profile_rows.get("vlm", [])
    combined_csv = manifest_root / "manifest.dual.csv"
    combined_json = manifest_root / "manifest.dual.json"
    _write_combined_csv(combined_rows, combined_csv)
    _write_combined_json(combined_rows, combined_json)

    print("\n=== Dual Summary ===")
    for profile in ("pipeline", "vlm"):
        summary = _summarize(profile_rows.get(profile, []))
        code = exit_codes.get(profile, 1)
        print(
            f"{profile}: exit_code={code}, total={summary['total']}, "
            f"success={summary['success']}, failed={summary['failed']}, "
            f"skipped={summary['skipped']}, with_md={summary['with_md']}"
        )

    dual_summary = _summarize(combined_rows)
    print(
        "combined: "
        f"total={dual_summary['total']}, success={dual_summary['success']}, "
        f"failed={dual_summary['failed']}, skipped={dual_summary['skipped']}, "
        f"with_md={dual_summary['with_md']}"
    )
    print(f"Combined manifest CSV: {combined_csv}")
    print(f"Combined manifest JSON: {combined_json}")

    return 0 if all(code == 0 for code in exit_codes.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
