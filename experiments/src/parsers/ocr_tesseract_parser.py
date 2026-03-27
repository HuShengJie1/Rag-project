from __future__ import annotations

import io
import time
from pathlib import Path

from .base import BaseParser, ParseResult


class TesseractOCRParser(BaseParser):
    name = "ocr_tesseract"

    def parse(self, file_path: str | Path, config: dict | None = None) -> ParseResult:
        start = time.perf_counter()
        result = ParseResult(parser_name=self.name)
        cfg = config or {}

        try:
            import fitz  # pymupdf
            import pytesseract
            from PIL import Image
        except Exception as e:
            result.success = False
            result.error_message = f"Missing OCR dependencies: {e}"
            result.elapsed_time = time.perf_counter() - start
            return result

        try:
            tesseract_cmd = cfg.get("tesseract_cmd")
            if tesseract_cmd:
                pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

            lang = cfg.get("lang", "chi_sim+eng")
            dpi = int(cfg.get("dpi", 200))

            path = Path(file_path)
            doc = fitz.open(path)
            texts = []
            for idx, page in enumerate(doc, start=1):
                pix = page.get_pixmap(dpi=dpi)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                text = pytesseract.image_to_string(img, lang=lang) or ""
                texts.append(text)
                result.structured_blocks.append({
                    "block_type": "ocr_page",
                    "text": text,
                    "page_no": idx,
                })
                result.page_metadata.append({
                    "page_no": idx,
                    "text_length": len(text),
                    "ocr_lang": lang,
                    "dpi": dpi,
                })
            result.raw_text = "\n\n".join(texts)
        except Exception as e:
            result.success = False
            result.error_message = str(e)
        finally:
            result.elapsed_time = time.perf_counter() - start
        return result
