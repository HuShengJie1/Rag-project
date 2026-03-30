from __future__ import annotations

import time
from pathlib import Path

from .base import BaseParser, ParseResult


class PyMuPDF4LLMParser(BaseParser):
    name = "pymupdf4llm"

    def parse(self, file_path: str | Path, config: dict | None = None) -> ParseResult:
        start = time.perf_counter()
        result = ParseResult(parser_name=self.name)
        try:
            import pymupdf4llm
        except Exception as e:
            result.success = False
            result.error_message = f"Missing dependency: pymupdf4llm ({e})"
            result.elapsed_time = time.perf_counter() - start
            return result

        try:
            path = Path(file_path)
            md = pymupdf4llm.to_markdown(str(path))
            result.markdown = md
            result.raw_text = md or ""
            result.structured_blocks.append({
                "block_type": "markdown",
                "text": md or "",
                "page_no": None,
            })
        except Exception as e:
            result.success = False
            result.error_message = str(e)
        finally:
            result.elapsed_time = time.perf_counter() - start
        return result
