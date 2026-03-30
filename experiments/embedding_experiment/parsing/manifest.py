from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

MANIFEST_FIELDS = [
    "file_id",
    "file_name",
    "absolute_path",
    "relative_path",
    "file_type",
    "run_profile",
    "parse_status",
    "output_dir",
    "output_md_exists",
    "output_md_path",
    "error_message",
    "parsed_at",
    "backend",
    "attempts",
    "duration_ms",
    "file_size_bytes",
    "modified_time",
    "source_hash",
    "command",
]


@dataclass
class ManifestRecord:
    file_id: str
    file_name: str
    absolute_path: str
    relative_path: str
    file_type: str
    run_profile: str
    parse_status: str
    output_dir: str
    output_md_exists: bool
    output_md_path: str
    error_message: str
    parsed_at: str
    backend: str = ""
    attempts: int = 0
    duration_ms: int = 0
    file_size_bytes: int = 0
    modified_time: str = ""
    source_hash: str = ""
    command: str = ""

    def to_row(self) -> dict[str, str | int]:
        return asdict(self)


def make_file_id(relative_path: Path) -> str:
    return hashlib.sha1(relative_path.as_posix().encode("utf-8")).hexdigest()


def make_source_hash(absolute_path: Path, size_bytes: int, mtime: float) -> str:
    raw = f"{absolute_path.resolve().as_posix()}::{size_bytes}::{mtime}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def make_output_subdir(file_stem: str, file_id: str) -> str:
    # Keep names readable and stable, and avoid collisions by suffixing file_id.
    sanitized = re.sub(r"\s+", "_", file_stem.strip())
    sanitized = re.sub(r"[^A-Za-z0-9_\-\u4e00-\u9fff]+", "_", sanitized)
    sanitized = sanitized.strip("_") or "document"
    return f"{sanitized}__{file_id[:10]}"


def write_manifest_csv(records: list[ManifestRecord], output_csv: Path) -> None:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        for record in records:
            writer.writerow(record.to_row())


def write_manifest_json(records: list[ManifestRecord], output_json: Path) -> None:
    output_json.parent.mkdir(parents=True, exist_ok=True)
    payload = [record.to_row() for record in records]
    output_json.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def summarize_records(records: list[ManifestRecord]) -> dict[str, int]:
    counts = {"total": len(records), "success": 0, "failed": 0, "skipped": 0}
    for record in records:
        if record.parse_status in counts:
            counts[record.parse_status] += 1
    return counts
