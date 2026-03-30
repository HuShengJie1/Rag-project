from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from file_discovery import FileCandidate, discover_files
from logging_utils import setup_logging
from manifest import (
    ManifestRecord,
    make_file_id,
    make_output_subdir,
    make_source_hash,
    summarize_records,
    write_manifest_csv,
    write_manifest_json,
)
from mineru_runner import run_single_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run MinerU parsing in batch mode.")
    parser.add_argument("--input_dir", type=Path, help="Input documents directory.")
    parser.add_argument("--input_file", type=Path, default=None, help="Optional single input file.")
    parser.add_argument("--output_dir", required=True, type=Path, help="Base output directory.")
    parser.add_argument("--manifest", required=True, type=Path, help="Output manifest CSV path.")
    parser.add_argument("--manifest_json", type=Path, default=None, help="Optional manifest JSON path.")
    parser.add_argument(
        "--run_profile",
        default="single",
        help="Logical run profile label (e.g. pipeline or vlm) for manifest tracking.",
    )
    parser.add_argument(
        "--backend",
        choices=["auto", "pipeline"],
        default="auto",
        help="MinerU backend. Use 'pipeline' for CPU fallback mode.",
    )
    parser.add_argument("--include_docx", action="store_true", help="Include DOCX files.")
    parser.add_argument("--include_images", action="store_true", help="Include image files.")
    parser.add_argument("--dry_run", action="store_true", help="Print planned execution without calling MinerU.")
    parser.add_argument("--retries", type=int, default=0, help="Retry count for failed files.")
    parser.add_argument("--timeout_sec", type=int, default=None, help="Per-file timeout in seconds.")
    parser.add_argument(
        "--skip-existing",
        "--skip_existing",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Skip files whose output directory already has content.",
    )
    parser.add_argument("--mineru_bin", default="mineru", help="MinerU CLI executable.")
    parser.add_argument("--hf_cache_dir", type=Path, default=None, help="HF cache dir (typically .../hub).")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose console logs.")
    parser.add_argument(
        "--check-mineru",
        "--check_mineru",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Check MinerU executable before running.",
    )
    return parser.parse_args()


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_abs(path: Path) -> Path:
    return path.expanduser().resolve()


def _build_env_overrides(hf_cache_dir: Path | None) -> dict[str, str]:
    if hf_cache_dir is None:
        return {}
    hub_dir = _to_abs(hf_cache_dir)
    # Point MinerU/HF to local cache to avoid unnecessary downloads.
    return {"HUGGINGFACE_HUB_CACHE": str(hub_dir)}


def _has_existing_output(output_dir: Path) -> bool:
    return output_dir.exists() and any(output_dir.iterdir())


def _check_mineru_available(mineru_bin: str) -> bool:
    return shutil.which(mineru_bin) is not None


def _find_markdown_output(output_dir: Path) -> str:
    if not output_dir.exists():
        return ""
    md_candidates = sorted(output_dir.rglob("*.md"))
    if not md_candidates:
        return ""
    return str(md_candidates[0].resolve())


def main() -> int:
    args = parse_args()

    output_dir = _to_abs(args.output_dir)
    manifest_csv = _to_abs(args.manifest)
    manifest_json = _to_abs(args.manifest_json) if args.manifest_json else None

    if args.input_file is None and args.input_dir is None:
        print("Either --input_dir or --input_file must be provided.")
        return 2
    if args.input_file is not None and args.input_dir is not None:
        print("Use either --input_dir or --input_file, not both.")
        return 2

    input_dir = _to_abs(args.input_dir) if args.input_dir else None
    input_file = _to_abs(args.input_file) if args.input_file else None

    output_dir.mkdir(parents=True, exist_ok=True)
    log_dir = output_dir.parent / "logs"
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    logger, log_path = setup_logging(log_dir=log_dir, run_id=run_id, verbose=args.verbose)

    logger.info("Run ID: %s", run_id)
    if input_dir:
        logger.info("Input dir: %s", input_dir)
    if input_file:
        logger.info("Input file: %s", input_file)
    logger.info("Output dir: %s", output_dir)
    logger.info("Manifest CSV: %s", manifest_csv)
    if manifest_json:
        logger.info("Manifest JSON: %s", manifest_json)
    logger.info("Log file: %s", log_path)

    if input_dir:
        if not input_dir.exists():
            logger.error("Input directory does not exist: %s", input_dir)
            return 2
        if not input_dir.is_dir():
            logger.error("Input path is not a directory: %s", input_dir)
            return 2
    if input_file:
        if not input_file.exists():
            logger.error("Input file does not exist: %s", input_file)
            return 2
        if not input_file.is_file():
            logger.error("Input path is not a file: %s", input_file)
            return 2

    if args.check_mineru and not args.dry_run and not _check_mineru_available(args.mineru_bin):
        logger.error("MinerU executable not found in PATH: %s", args.mineru_bin)
        logger.error("Use --mineru_bin to specify path or install mineru first.")
        return 2

    env_overrides = _build_env_overrides(args.hf_cache_dir)
    if env_overrides:
        logger.info("Using local HF cache: %s", env_overrides["HUGGINGFACE_HUB_CACHE"])

    if input_file:
        single_type = input_file.suffix.lower().lstrip(".")
        if single_type not in {"pdf", "docx", "png", "jpg", "jpeg", "bmp", "tif", "tiff", "webp"}:
            logger.error("Unsupported input_file type: %s", input_file.suffix)
            return 2
        file_type = "image" if single_type in {"png", "jpg", "jpeg", "bmp", "tif", "tiff", "webp"} else single_type
        candidates = [
            FileCandidate(
                absolute_path=input_file,
                relative_path=Path(input_file.name),
                file_type=file_type,
            )
        ]
    else:
        candidates = discover_files(
            input_dir=input_dir,
            include_docx=args.include_docx,
            include_images=args.include_images,
        )
    logger.info("Discovered %d files to consider.", len(candidates))

    records: list[ManifestRecord] = []
    # Ensure manifest files exist even when no documents are discovered.
    write_manifest_csv(records, manifest_csv)
    if manifest_json:
        write_manifest_json(records, manifest_json)

    for idx, candidate in enumerate(candidates, start=1):
        file_id = make_file_id(candidate.relative_path)
        output_subdir = make_output_subdir(candidate.absolute_path.stem, file_id)
        per_file_output = output_dir / output_subdir

        stat = candidate.absolute_path.stat()
        source_hash = make_source_hash(candidate.absolute_path, stat.st_size, stat.st_mtime)

        logger.info(
            "[%d/%d] %s -> %s",
            idx,
            len(candidates),
            candidate.relative_path.as_posix(),
            per_file_output,
        )

        if args.skip_existing and _has_existing_output(per_file_output):
            md_output_path = _find_markdown_output(per_file_output)
            record = ManifestRecord(
                file_id=file_id,
                file_name=candidate.absolute_path.name,
                absolute_path=str(candidate.absolute_path),
                relative_path=candidate.relative_path.as_posix(),
                file_type=candidate.file_type,
                run_profile=args.run_profile,
                parse_status="skipped",
                output_dir=str(per_file_output),
                output_md_exists=bool(md_output_path),
                output_md_path=md_output_path,
                error_message="output exists, skipped",
                parsed_at=_now_utc_iso(),
                backend=args.backend,
                attempts=0,
                duration_ms=0,
                file_size_bytes=stat.st_size,
                modified_time=datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                source_hash=source_hash,
                command="",
            )
            records.append(record)
            write_manifest_csv(records, manifest_csv)
            if manifest_json:
                write_manifest_json(records, manifest_json)
            continue

        result = run_single_file(
            mineru_bin=args.mineru_bin,
            input_file=candidate.absolute_path,
            output_dir=per_file_output,
            backend=args.backend,
            retries=max(0, args.retries),
            dry_run=args.dry_run,
            timeout_sec=args.timeout_sec,
            env_overrides=env_overrides,
        )

        md_output_path = _find_markdown_output(per_file_output)
        record = ManifestRecord(
            file_id=file_id,
            file_name=candidate.absolute_path.name,
            absolute_path=str(candidate.absolute_path),
            relative_path=candidate.relative_path.as_posix(),
            file_type=candidate.file_type,
            run_profile=args.run_profile,
            parse_status=result.status,
            output_dir=str(per_file_output),
            output_md_exists=bool(md_output_path),
            output_md_path=md_output_path,
            error_message=result.error_message,
            parsed_at=result.finished_at,
            backend=args.backend,
            attempts=result.attempts,
            duration_ms=result.duration_ms,
            file_size_bytes=stat.st_size,
            modified_time=datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
            source_hash=source_hash,
            command=result.command,
        )
        records.append(record)

        if result.status == "success":
            logger.info("Success: %s", candidate.relative_path.as_posix())
        elif result.status == "skipped":
            logger.info("Skipped: %s (%s)", candidate.relative_path.as_posix(), result.error_message)
        else:
            logger.error("Failed: %s | %s", candidate.relative_path.as_posix(), result.error_message)

        # Persist incrementally so interrupted runs still have traceable state.
        write_manifest_csv(records, manifest_csv)
        if manifest_json:
            write_manifest_json(records, manifest_json)

    summary = summarize_records(records)
    logger.info(
        "Summary | total=%d success=%d failed=%d skipped=%d",
        summary["total"],
        summary["success"],
        summary["failed"],
        summary["skipped"],
    )

    print(
        "Batch parsing completed: "
        f"total={summary['total']}, success={summary['success']}, "
        f"failed={summary['failed']}, skipped={summary['skipped']}"
    )
    print(f"Manifest CSV: {manifest_csv}")
    if manifest_json:
        print(f"Manifest JSON: {manifest_json}")
    print(f"Log file: {log_path}")

    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
