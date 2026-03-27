from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass
class GroundTruthRecord:
    doc_id: str
    gt_path: Path
    gt_type: str
    source_parser: str = ""

    def to_row(self) -> dict[str, str]:
        return {
            "doc_id": self.doc_id,
            "gt_path": str(self.gt_path),
            "gt_type": self.gt_type,
            "source_parser": self.source_parser,
        }


class GroundTruthRegistry:
    def __init__(self, records: list[GroundTruthRecord] | None = None) -> None:
        self._records = {record.doc_id: record for record in (records or [])}
        self._missing_doc_ids: set[str] = set()

    @classmethod
    def from_manifest(cls, manifest_path: str | Path) -> "GroundTruthRegistry":
        path = Path(manifest_path)
        if not path.exists():
            return cls([])

        records: list[GroundTruthRecord] = []
        with path.open("r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                doc_id = (row.get("doc_id") or "").strip()
                gt_path = (row.get("gt_path") or "").strip()
                gt_type = (row.get("gt_type") or "").strip()
                source_parser = (row.get("source_parser") or "").strip()
                if not doc_id or not gt_path or not gt_type:
                    continue
                records.append(
                    GroundTruthRecord(
                        doc_id=doc_id,
                        gt_path=Path(gt_path),
                        gt_type=gt_type,
                        source_parser=source_parser,
                    )
                )
        return cls(records)

    def get(self, doc_id: str) -> GroundTruthRecord | None:
        record = self._records.get(str(doc_id))
        if record is None:
            self._missing_doc_ids.add(str(doc_id))
        return record

    def read_text(self, doc_id: str) -> str | None:
        record = self.get(doc_id)
        if record is None:
            return None
        try:
            return record.gt_path.read_text(encoding="utf-8")
        except Exception:
            return None

    def missing_doc_ids(self) -> list[str]:
        return sorted(self._missing_doc_ids, key=lambda x: (len(x), x))

    def all_records(self) -> list[GroundTruthRecord]:
        return list(self._records.values())
