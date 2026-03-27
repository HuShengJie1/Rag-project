from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterable

import requests


def _safe_filename(text: str) -> str:
    return "".join(c if c.isalnum() or c in "._-" else "_" for c in text)


def _guess_ext(url: str) -> str:
    suffix = Path(url).suffix
    if suffix and len(suffix) <= 5:
        return suffix
    return ".pdf"


def _hash_url(url: str) -> str:
    return hashlib.md5(url.encode("utf-8")).hexdigest()[:12]


def download_file(url: str, target_dir: Path, name_hint: str | None = None, timeout: int = 60) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    ext = _guess_ext(url)
    base = _safe_filename(name_hint) if name_hint else _hash_url(url)
    path = target_dir / f"{base}{ext}"
    if path.exists():
        return path

    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    path.write_bytes(resp.content)
    return path


def batch_download(
    rows: Iterable[dict],
    url_key: str,
    out_dir: Path,
    id_key: str = "doc_id",
    timeout: int = 60,
) -> dict[str, Path]:
    mapping: dict[str, Path] = {}
    for row in rows:
        url = row.get(url_key)
        if not url:
            continue
        doc_id = str(row.get(id_key) or "")
        name_hint = doc_id if doc_id else None
        path = download_file(str(url), out_dir, name_hint=name_hint, timeout=timeout)
        mapping[doc_id] = path
    return mapping
