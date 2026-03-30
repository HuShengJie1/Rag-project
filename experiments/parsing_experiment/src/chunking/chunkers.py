from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Iterable


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    text: str
    chunk_index: int
    metadata: dict[str, Any]

    def to_record(self) -> dict[str, Any]:
        data = asdict(self)
        return data


def chunk_by_chars(text: str, chunk_size: int = 800, overlap: int = 100) -> list[str]:
    if not text:
        return []
    chunks = []
    step = max(1, chunk_size - overlap)
    for start in range(0, len(text), step):
        chunk = text[start:start + chunk_size]
        if chunk:
            chunks.append(chunk)
    return chunks


def _split_markdown_by_headings(markdown: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    current_heading = ""
    buffer: list[str] = []
    for line in markdown.splitlines():
        if line.strip().startswith("#"):
            if buffer:
                sections.append((current_heading, "\n".join(buffer).strip()))
                buffer = []
            current_heading = line.strip()
        else:
            buffer.append(line)
    if buffer:
        sections.append((current_heading, "\n".join(buffer).strip()))
    return sections


def chunk_document(
    normalized_doc: dict[str, Any],
    strategy: str = "chars",
    config: dict[str, Any] | None = None,
) -> list[Chunk]:
    config = config or {}
    chunk_size = int(config.get("chunk_size", 800))
    overlap = int(config.get("overlap", 100))

    doc_id = normalized_doc.get("doc_id", "")
    source_path = normalized_doc.get("source_path", "")
    parser_name = normalized_doc.get("parser_name", "")
    blocks = normalized_doc.get("blocks", [])

    chunks: list[Chunk] = []
    idx = 0
    for block in blocks:
        text = block.get("text", "") or ""
        block_type = block.get("block_type", "text")
        page_no = block.get("page_no")
        metadata = block.get("metadata", {})

        if strategy == "heading" and block_type == "markdown":
            sections = _split_markdown_by_headings(text)
            for heading, content in sections:
                for piece in chunk_by_chars(content, chunk_size, overlap):
                    idx += 1
                    chunks.append(Chunk(
                        chunk_id=f"{doc_id}-{idx:05d}",
                        doc_id=doc_id,
                        text=piece,
                        chunk_index=idx,
                        metadata={
                            "source_path": source_path,
                            "parser_name": parser_name,
                            "block_type": block_type,
                            "page_no": page_no,
                            "heading": heading,
                            **metadata,
                        },
                    ))
        else:
            for piece in chunk_by_chars(text, chunk_size, overlap):
                idx += 1
                chunks.append(Chunk(
                    chunk_id=f"{doc_id}-{idx:05d}",
                    doc_id=doc_id,
                    text=piece,
                    chunk_index=idx,
                    metadata={
                        "source_path": source_path,
                        "parser_name": parser_name,
                        "block_type": block_type,
                        "page_no": page_no,
                        **metadata,
                    },
                ))
    return chunks


def save_chunks_jsonl(chunks: Iterable[Chunk], path: Path) -> None:
    from utils.io import write_jsonl
    write_jsonl(path, [c.to_record() for c in chunks])


def save_chunks_csv(chunks: Iterable[Chunk], path: Path) -> None:
    from utils.io import write_csv
    rows = [c.to_record() for c in chunks]
    fieldnames = ["chunk_id", "doc_id", "chunk_index", "text", "metadata"]
    # flatten metadata to string
    for r in rows:
        r["metadata"] = str(r.get("metadata", {}))
    write_csv(path, rows, fieldnames)
