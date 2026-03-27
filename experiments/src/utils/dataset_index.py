from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


def _norm_header(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower().replace(" ", "").replace("_", "").replace("-", "")


def _split_tags(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(v).strip() for v in value if str(v).strip()]
    text = str(value).strip()
    if not text:
        return []
    for sep in [",", "，", ";", "；", "|", "/", " "]:
        text = text.replace(sep, ",")
    return [t for t in (x.strip() for x in text.split(",")) if t]


def _build_tags_from_row(row: dict[str, Any]) -> list[str]:
    tags: list[str] = []
    for key in ["scan_status", "document_type", "category", "table_density", "structure_complexity"]:
        if key in row and row[key]:
            tags.append(str(row[key]).strip())

    scan = str(row.get("scan_status", "")).strip().lower()
    if scan in {"native_text", "text_native"}:
        tags.append("text_native")
    elif scan in {"scanned_ocr", "scan_ocr", "ocr"}:
        tags.append("scanned_ocr")

    table_density = str(row.get("table_density", "")).strip().lower()
    if table_density in {"high", "very_high", "medium_high"}:
        tags.append("table_rich")

    doc_type = str(row.get("document_type", "")).strip().lower()
    if "大纲" in doc_type or "syllabus" in doc_type:
        tags.append("syllabus")
    if "达成" in doc_type or "attainment" in doc_type:
        tags.append("attainment_report")

    seen = set()
    unique = []
    for t in tags:
        if t and t not in seen:
            seen.add(t)
            unique.append(t)
    return unique


@dataclass
class DocumentMeta:
    doc_id: str
    file_path: Path | None
    file_type: str
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    source_url: str | None = None
    valid: bool = True
    errors: list[str] = field(default_factory=list)

    def to_record(self) -> dict[str, Any]:
        data = asdict(self)
        data["file_path"] = str(self.file_path) if self.file_path else ""
        data["tags"] = ",".join(self.tags)
        data["errors"] = "; ".join(self.errors)
        return data


@dataclass
class DatasetIndex:
    documents: list[DocumentMeta]
    errors: list[str] = field(default_factory=list)

    def filter_by_tags(self, tags: list[str]) -> "DatasetIndex":
        if not tags:
            return self
        normalized = {t.lower() for t in tags}
        docs = [
            d
            for d in self.documents
            if any(t.lower() in normalized for t in d.tags)
        ]
        return DatasetIndex(documents=docs, errors=self.errors)


def _resolve_metadata_path(path: Path | None, base_dir: Path) -> Path:
    if path and path.exists():
        return path
    # Fallback: search for any xlsx in base_dir
    candidates = list(base_dir.glob("*.xlsx"))
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        for c in candidates:
            name = c.name
            if "实验元数据" in name or "元数据" in name:
                return c
    raise FileNotFoundError(
        f"Metadata Excel not found. Use --metadata or place a single .xlsx under {base_dir}."
    )


def _read_xlsx(path: Path, sheet: str | None = None) -> list[dict[str, Any]]:
    try:
        import openpyxl
    except Exception as e:
        raise ImportError("Missing dependency: openpyxl. Install with `pip install openpyxl`.") from e

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb[sheet] if sheet else wb.active
    rows = ws.iter_rows(values_only=True)
    try:
        headers = next(rows)
    except StopIteration:
        return []
    header_keys = [str(h).strip() if h is not None else "" for h in headers]
    records: list[dict[str, Any]] = []
    for row in rows:
        record = {}
        for idx, value in enumerate(row):
            if idx < len(header_keys) and header_keys[idx]:
                record[header_keys[idx]] = value
        if record:
            records.append(record)
    return records


def _pick_column(headers: list[str], candidates: list[str]) -> str | None:
    norm_map = {_norm_header(h): h for h in headers}
    for c in candidates:
        key = _norm_header(c)
        if key in norm_map:
            return norm_map[key]
    # fuzzy
    for h in headers:
        nh = _norm_header(h)
        for c in candidates:
            if _norm_header(c) in nh:
                return h
    return None


def load_dataset_index(
    metadata_path: Path | None,
    root_dir: Path | None = None,
    sheet: str | None = None,
    column_map: dict[str, str] | None = None,
    default_download_dir: Path | None = None,
) -> DatasetIndex:
    base_dir = Path(metadata_path).parent if metadata_path else Path("experiments")
    path = _resolve_metadata_path(metadata_path, base_dir)

    records = _read_xlsx(path, sheet=sheet)
    if not records:
        return DatasetIndex(documents=[], errors=["metadata is empty"])

    headers = list(records[0].keys())
    doc_id_col = column_map.get("doc_id") if column_map else None
    path_col = column_map.get("file_path") if column_map else None
    tags_col = column_map.get("tags") if column_map else None
    type_col = column_map.get("file_type") if column_map else None

    doc_id_col = doc_id_col or _pick_column(
        headers, ["doc_id", "id", "文档id", "文档ID", "编号", "文件id", "文件ID"]
    )
    path_col = path_col or _pick_column(
        headers, ["file_path", "path", "filepath", "文件路径", "路径", "文件", "文档路径", "local_path", "本地路径"]
    )
    url_col = _pick_column(headers, ["url", "URL", "链接", "下载地址"])
    tags_col = tags_col or _pick_column(
        headers, ["tags", "标签", "label", "labels", "类型", "类别", "子集", "subset"]
    )
    type_col = type_col or _pick_column(
        headers, ["file_type", "类型", "格式", "后缀", "ext", "file_format"]
    )

    root_dir = root_dir or path.parent

    documents: list[DocumentMeta] = []
    errors: list[str] = []
    if path_col is None:
        errors.append("file_path column not found in metadata")

    for idx, row in enumerate(records, start=1):
        doc_id = row.get(doc_id_col) if doc_id_col else None
        if doc_id is None or str(doc_id).strip() == "":
            doc_id = f"doc_{idx:03d}"

        raw_path = row.get(path_col) if path_col else None
        source_url = row.get(url_col) if url_col else None
        file_path: Path | None = None

        if raw_path:
            try:
                file_path = Path(str(raw_path))
            except Exception:
                file_path = None
        elif source_url and isinstance(source_url, str):
            if not source_url.lower().startswith(("http://", "https://")):
                file_path = Path(source_url)
            elif default_download_dir:
                ext = Path(source_url).suffix or ""
                file_path = (default_download_dir / f"{doc_id}{ext}").resolve()

        if file_path and not file_path.is_absolute():
            file_path = (root_dir / file_path).resolve()

        if (doc_id == f"doc_{idx:03d}") and file_path and file_path.name:
            doc_id = file_path.stem

        tags = _split_tags(row.get(tags_col)) if tags_col else _build_tags_from_row(row)
        file_type = row.get(type_col) if type_col else None
        file_type = str(file_type).strip().lower() if file_type else (file_path.suffix.lower().lstrip(".") if file_path else "")

        meta = DocumentMeta(
            doc_id=str(doc_id),
            file_path=file_path,
            file_type=file_type,
            tags=tags,
            metadata=row,
            source_url=str(source_url).strip() if source_url else None,
        )

        # Basic validations
        if not file_path:
            meta.valid = False
            if source_url:
                meta.errors.append("file_path missing (url present)")
            else:
                meta.errors.append("file_path missing")
        elif not file_path.exists() or not file_path.is_file():
            meta.valid = False
            meta.errors.append("file path does not exist")
        if not file_type:
            meta.valid = False
            meta.errors.append("file type not detected")

        documents.append(meta)

    return DatasetIndex(documents=documents, errors=errors)
