from __future__ import annotations

import time
from pathlib import Path

from .base import BaseParser, ParseResult


class PyMuPDFParser(BaseParser):
    name = "pymupdf"

    def parse(self, file_path: str | Path, config: dict | None = None) -> ParseResult:
        start = time.perf_counter()
        result = ParseResult(parser_name=self.name)
        try:
            import fitz  # pymupdf
        except Exception as e:
            result.success = False
            result.error_message = f"Missing dependency: pymupdf ({e})"
            result.elapsed_time = time.perf_counter() - start
            return result

        try:
            path = Path(file_path)
            doc = fitz.open(path)
            texts = []
            for idx, page in enumerate(doc, start=1):
                text = page.get_text("text") or ""
                texts.append(text)
                result.structured_blocks.append({
                    "block_type": "page",
                    "text": text,
                    "page_no": idx,
                })
                result.page_metadata.append({
                    "page_no": idx,
                    "text_length": len(text),
                })
            result.raw_text = "\n\n".join(texts)
        except Exception as e:
            result.success = False
            result.error_message = str(e)
        finally:
            result.elapsed_time = time.perf_counter() - start
        return result
