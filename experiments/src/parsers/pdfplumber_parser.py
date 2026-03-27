from __future__ import annotations

import time
from pathlib import Path

from .base import BaseParser, ParseResult


class PDFPlumberParser(BaseParser):
    name = "pdfplumber"

    def parse(self, file_path: str | Path, config: dict | None = None) -> ParseResult:
        start = time.perf_counter()
        result = ParseResult(parser_name=self.name)
        try:
            import pdfplumber
        except Exception as e:
            result.success = False
            result.error_message = f"Missing dependency: pdfplumber ({e})"
            result.elapsed_time = time.perf_counter() - start
            return result

        try:
            path = Path(file_path)
            texts = []
            with pdfplumber.open(path) as pdf:
                for idx, page in enumerate(pdf.pages, start=1):
                    text = page.extract_text() or ""
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
