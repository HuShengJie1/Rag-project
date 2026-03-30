from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

try:
    from langchain_text_splitters import (
        MarkdownHeaderTextSplitter,
        RecursiveCharacterTextSplitter,
    )
except ImportError:  # pragma: no cover
    from langchain.text_splitter import (  # type: ignore
        MarkdownHeaderTextSplitter,
        RecursiveCharacterTextSplitter,
    )


DEFAULT_HEADERS_TO_SPLIT_ON = [
    ("#", "h1"),
    ("##", "h2"),
    ("###", "h3"),
    ("####", "h4"),
]


def _clean_markdown(text: str) -> str:
    text = text.replace("\r\n", "\n")
    text = re.sub(r"^\s*====\s*PAGE_\d+_(START|END)\s*====\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_markdown_text(
    markdown_text: str,
    *,
    original_doc_id: str,
    source: str,
    headers_to_split_on: list[tuple[str, str]] | None = None,
    chunk_size: int = 700,
    chunk_overlap: int = 120,
    min_chunk_chars: int = 20,
) -> list[dict]:
    headers = headers_to_split_on or DEFAULT_HEADERS_TO_SPLIT_ON
    cleaned_text = _clean_markdown(markdown_text)

    header_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=headers,
        strip_headers=False,
    )
    recursive_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", "。", "；", "，", " ", ""],
    )

    header_docs = header_splitter.split_text(cleaned_text)
    if not header_docs:
        header_docs = []

    chunks: list[dict] = []
    chunk_counter = 0
    header_keys = [name for _, name in headers]

    for header_index, doc in enumerate(header_docs):
        metadata = dict(doc.metadata or {})
        header_hierarchy = [str(metadata.get(k, "")).strip() for k in header_keys if str(metadata.get(k, "")).strip()]
        section_title = header_hierarchy[-1] if header_hierarchy else ""
        section_text = doc.page_content.strip()

        if not section_text:
            continue

        if len(section_text) > chunk_size:
            split_texts = recursive_splitter.split_text(section_text)
            split_stage = "recursive_split"
        else:
            split_texts = [section_text]
            split_stage = "header_split"

        for local_index, chunk_text in enumerate(split_texts):
            chunk_text = chunk_text.strip()
            if len(chunk_text) < min_chunk_chars:
                continue
            chunk_counter += 1
            chunks.append(
                {
                    "chunk_id": f"{original_doc_id}::chunk_{chunk_counter:04d}",
                    "original_doc_id": original_doc_id,
                    "source": source,
                    "section_title": section_title,
                    "header_hierarchy": header_hierarchy,
                    "chunk_index_in_doc": chunk_counter,
                    "header_block_index": header_index,
                    "sub_chunk_index": local_index,
                    "split_stage": split_stage,
                    "text": chunk_text,
                }
            )

    return chunks


def split_markdown_file(
    file_path: str | Path,
    *,
    headers_to_split_on: list[tuple[str, str]] | None = None,
    chunk_size: int = 700,
    chunk_overlap: int = 120,
    min_chunk_chars: int = 20,
) -> list[dict]:
    path = Path(file_path)
    text = path.read_text(encoding="utf-8")
    return split_markdown_text(
        text,
        original_doc_id=path.name,
        source=str(path),
        headers_to_split_on=headers_to_split_on,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        min_chunk_chars=min_chunk_chars,
    )


def build_chunk_corpus(
    md_dir: str | Path,
    *,
    selected_doc_ids: Iterable[str] | None = None,
    headers_to_split_on: list[tuple[str, str]] | None = None,
    chunk_size: int = 700,
    chunk_overlap: int = 120,
    min_chunk_chars: int = 20,
) -> list[dict]:
    md_path = Path(md_dir)
    if not md_path.exists():
        raise FileNotFoundError(f"Markdown directory does not exist: {md_path}")

    selected = set(selected_doc_ids) if selected_doc_ids else None
    chunks: list[dict] = []

    for file_path in sorted(md_path.glob("*.md")):
        if selected is not None and file_path.name not in selected:
            continue
        chunks.extend(
            split_markdown_file(
                file_path,
                headers_to_split_on=headers_to_split_on,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                min_chunk_chars=min_chunk_chars,
            )
        )

    return chunks
