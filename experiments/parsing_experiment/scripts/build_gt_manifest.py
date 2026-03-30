from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from evaluation.ground_truth import GroundTruthRecord
from utils.io import ensure_dir, write_csv, write_text
from utils.logging import get_logger


SUPPORTED_EXTS = {".md", ".markdown", ".txt", ".json"}


@dataclass
class ManifestDoc:
    doc_id: str
    doc_dir: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build ground truth manifest for parsing evaluation.")
    parser.add_argument("--manifest", type=str, default="experiments/parsing_eval/manifest.csv")
    parser.add_argument("--ground-truth-root", type=str, default="experiments/parsing_eval/ground_truth")
    parser.add_argument("--output-manifest", type=str, default="experiments/parsing_eval/ground_truth/gt_manifest.csv")
    parser.add_argument("--output-report", type=str, default="experiments/parsing_eval/ground_truth/gt_report.md")
    return parser.parse_args()


def read_manifest_docs(path: Path) -> list[ManifestDoc]:
    with path.open("r", encoding="utf-8") as f:
        return [
            ManifestDoc(doc_id=(row.get("doc_id") or "").strip(), doc_dir=(row.get("doc_dir") or "").strip())
            for row in csv.DictReader(f)
            if (row.get("doc_id") or "").strip()
        ]


def normalize_name(text: str) -> str:
    return "".join(ch.lower() for ch in text if not ch.isspace())


def choose_primary_file(path: Path) -> Path | None:
    if path.is_file() and path.suffix.lower() in SUPPORTED_EXTS:
        return path
    if not path.is_dir():
        return None

    preferred = ["ground_truth.md", "gt.md", "ground_truth.txt", "gt.txt", "ground_truth.json", "gt.json"]
    for name in preferred:
        candidate = path / name
        if candidate.exists() and candidate.is_file():
            return candidate

    files = sorted([item for item in path.iterdir() if item.is_file() and item.suffix.lower() in SUPPORTED_EXTS])
    return files[0] if files else None


def parse_pseudo_source_parser(item: Path) -> str:
    meta_candidates = [item / "meta.json", item / "gt_meta.json"] if item.is_dir() else []
    for meta_path in meta_candidates:
        if not meta_path.exists():
            continue
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
            parser_name = str(data.get("source_parser") or "").strip()
            if parser_name:
                return parser_name
        except Exception:
            continue

    if item.parent and item.parent.name not in {"pseudo_gt", "manual_gt"}:
        return item.parent.name
    return ""


def scan_gt_records(gt_root: Path, manifest_docs: list[ManifestDoc], logger: Any) -> list[GroundTruthRecord]:
    manual_root = ensure_dir(gt_root / "manual_gt")
    pseudo_root = ensure_dir(gt_root / "pseudo_gt")

    doc_id_lookup = {doc.doc_id: doc for doc in manifest_docs}
    doc_dir_lookup = {normalize_name(doc.doc_dir): doc for doc in manifest_docs if doc.doc_dir}

    records: list[GroundTruthRecord] = []
    seen_doc_ids: set[str] = set()

    def match_doc(item: Path) -> ManifestDoc | None:
        name = item.stem if item.is_file() else item.name
        if name in doc_id_lookup:
            return doc_id_lookup[name]
        normalized = normalize_name(name)
        if normalized in doc_dir_lookup:
            return doc_dir_lookup[normalized]
        for key, doc in doc_dir_lookup.items():
            if normalized == key or normalized in key or key in normalized:
                return doc
        return None

    def handle_item(item: Path, gt_type: str) -> None:
        file_path = choose_primary_file(item)
        if file_path is None:
            return
        doc = match_doc(item)
        if doc is None:
            logger.warning("Ground truth item not matched to manifest: %s", item)
            return
        if doc.doc_id in seen_doc_ids:
            logger.warning("Duplicate ground truth mapping for doc_id=%s, keeping first match", doc.doc_id)
            return
        seen_doc_ids.add(doc.doc_id)
        records.append(
            GroundTruthRecord(
                doc_id=doc.doc_id,
                gt_path=file_path.resolve(),
                gt_type=gt_type,
                source_parser=parse_pseudo_source_parser(item) if gt_type == "pseudo_gt" else "",
            )
        )

    for item in sorted(manual_root.iterdir()) if manual_root.exists() else []:
        handle_item(item, "manual_gt")
    for item in sorted(pseudo_root.iterdir()) if pseudo_root.exists() else []:
        if item.is_dir() and item.name not in doc_id_lookup:
            nested_items = sorted(item.iterdir())
            if nested_items and all(child.is_dir() or child.is_file() for child in nested_items):
                for child in nested_items:
                    handle_item(child, "pseudo_gt")
                continue
        handle_item(item, "pseudo_gt")

    return sorted(records, key=lambda x: (len(x.doc_id), x.doc_id))


def build_report(manifest_docs: list[ManifestDoc], records: list[GroundTruthRecord]) -> str:
    manual_docs = [record.doc_id for record in records if record.gt_type == "manual_gt"]
    pseudo_docs = [record.doc_id for record in records if record.gt_type == "pseudo_gt"]
    covered = {record.doc_id for record in records}
    missing_docs = [doc.doc_id for doc in manifest_docs if doc.doc_id not in covered]

    lines: list[str] = []
    lines.append("# Ground Truth Report")
    lines.append("")
    lines.append(f"- Total manifest docs: {len(manifest_docs)}")
    lines.append(f"- manual_gt docs: {len(manual_docs)}")
    lines.append(f"- pseudo_gt docs: {len(pseudo_docs)}")
    lines.append(f"- no_gt docs: {len(missing_docs)}")
    lines.append("")
    lines.append("## manual_gt")
    if manual_docs:
        lines.extend(f"- {doc_id}" for doc_id in manual_docs)
    else:
        lines.append("- None")
    lines.append("")
    lines.append("## pseudo_gt")
    if pseudo_docs:
        pseudo_map = {record.doc_id: record.source_parser for record in records if record.gt_type == "pseudo_gt"}
        for doc_id in pseudo_docs:
            source_parser = pseudo_map.get(doc_id, "")
            suffix = f" (source_parser={source_parser})" if source_parser else ""
            lines.append(f"- {doc_id}{suffix}")
    else:
        lines.append("- None")
    lines.append("")
    lines.append("## no_gt")
    if missing_docs:
        lines.extend(f"- {doc_id}" for doc_id in missing_docs)
    else:
        lines.append("- None")
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    manifest_path = Path(args.manifest).resolve()
    gt_root = Path(args.ground_truth_root).resolve()
    output_manifest = Path(args.output_manifest).resolve()
    output_report = Path(args.output_report).resolve()
    logger = get_logger("build_gt_manifest", ROOT / "outputs" / "logs" / "build_gt_manifest.log")

    ensure_dir(gt_root / "manual_gt")
    ensure_dir(gt_root / "pseudo_gt")

    manifest_docs = read_manifest_docs(manifest_path)
    records = scan_gt_records(gt_root, manifest_docs, logger)

    rows = [record.to_row() for record in records]
    write_csv(output_manifest, rows, ["doc_id", "gt_path", "gt_type", "source_parser"])
    write_text(output_report, build_report(manifest_docs, records))
    logger.info("Built gt manifest with %s records", len(records))


if __name__ == "__main__":
    main()
