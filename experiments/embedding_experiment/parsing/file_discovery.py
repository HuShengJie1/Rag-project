from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

PDF_EXTENSIONS = {".pdf"}
DOCX_EXTENSIONS = {".docx"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}

HIDDEN_OR_TEMP_PREFIXES = (".", "~$")
HIDDEN_OR_TEMP_SUFFIXES = ("~", ".tmp", ".swp", ".ds_store")


@dataclass(frozen=True)
class FileCandidate:
    absolute_path: Path
    relative_path: Path
    file_type: str


def _is_hidden_or_temp(path: Path) -> bool:
    name = path.name.lower()
    return name.startswith(HIDDEN_OR_TEMP_PREFIXES) or name.endswith(HIDDEN_OR_TEMP_SUFFIXES)


def _infer_file_type(path: Path) -> str | None:
    suffix = path.suffix.lower()
    if suffix in PDF_EXTENSIONS:
        return "pdf"
    if suffix in DOCX_EXTENSIONS:
        return "docx"
    if suffix in IMAGE_EXTENSIONS:
        return "image"
    return None


def discover_files(
    input_dir: Path,
    *,
    include_docx: bool = False,
    include_images: bool = False,
) -> list[FileCandidate]:
    candidates: list[FileCandidate] = []

    for path in sorted(input_dir.rglob("*")):
        if not path.is_file():
            continue

        if _is_hidden_or_temp(path):
            continue

        if any(part.startswith(".") for part in path.relative_to(input_dir).parts):
            continue

        file_type = _infer_file_type(path)
        if file_type is None:
            continue
        if file_type == "docx" and not include_docx:
            continue
        if file_type == "image" and not include_images:
            continue

        candidates.append(
            FileCandidate(
                absolute_path=path.resolve(),
                relative_path=path.relative_to(input_dir),
                file_type=file_type,
            )
        )

    return candidates
