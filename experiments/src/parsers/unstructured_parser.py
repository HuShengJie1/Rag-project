from __future__ import annotations

import time
from pathlib import Path

from .base import BaseParser, ParseResult


class UnstructuredParser(BaseParser):
    name = "unstructured"

    def parse(self, file_path: str | Path, config: dict | None = None) -> ParseResult:
        start = time.perf_counter()
        result = ParseResult(parser_name=self.name)
        try:
            from unstructured.partition.pdf import partition_pdf
        except Exception as e:
            result.success = False
            result.error_message = f"Missing dependency: unstructured ({e})"
            result.elapsed_time = time.perf_counter() - start
            return result

        try:
            path = Path(file_path)
            elements = partition_pdf(filename=str(path), **(config or {}))
            texts = []
            for el in elements:
                text = str(el).strip()
                if not text:
                    continue
                page_no = None
                block_type = getattr(el, "category", "element")
                metadata = getattr(el, "metadata", None)
                if metadata and hasattr(metadata, "page_number"):
                    page_no = metadata.page_number
                result.structured_blocks.append({
                    "block_type": block_type,
                    "text": text,
                    "page_no": page_no,
                })
                texts.append(text)
            result.raw_text = "\n\n".join(texts)
        except Exception as e:
            result.success = False
            result.error_message = str(e)
        finally:
            result.elapsed_time = time.perf_counter() - start
        return result
