from __future__ import annotations

from typing import Any
from pathlib import Path

from parsers.base import ParseResult


def normalize_parse_result(
    doc_id: str,
    file_path: str | Path,
    result: ParseResult,
) -> dict[str, Any]:
    blocks: list[dict[str, Any]] = []

    if result.structured_blocks:
        for b in result.structured_blocks:
            blocks.append({
                "block_type": b.get("block_type", "text"),
                "text": b.get("text", "") or "",
                "page_no": b.get("page_no"),
                "metadata": {k: v for k, v in b.items() if k not in {"block_type", "text", "page_no"}},
            })
    else:
        text = result.markdown or result.raw_text or ""
        blocks.append({
            "block_type": "markdown" if result.markdown else "text",
            "text": text,
            "page_no": None,
            "metadata": {},
        })

    pages = result.page_metadata or []

    return {
        "doc_id": doc_id,
        "source_path": str(file_path),
        "parser_name": result.parser_name,
        "pages": pages,
        "blocks": blocks,
    }
