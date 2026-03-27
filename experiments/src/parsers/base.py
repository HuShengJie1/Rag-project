from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ParseResult:
    raw_text: str = ""
    markdown: str | None = None
    structured_blocks: list[dict[str, Any]] = field(default_factory=list)
    page_metadata: list[dict[str, Any]] = field(default_factory=list)
    parser_name: str = ""
    elapsed_time: float = 0.0
    success: bool = True
    error_message: str | None = None


class BaseParser:
    name = "base"

    def parse(self, file_path: str | Path, config: dict | None = None) -> ParseResult:
        raise NotImplementedError
