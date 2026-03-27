from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any


TITLE_PATTERNS = [
    re.compile(r"^\s{0,3}#{1,6}\s+.+$"),
    re.compile(r"^\s*[一二三四五六七八九十]+、.+$"),
    re.compile(r"^\s*（[一二三四五六七八九十]+）.+$"),
    re.compile(r"^\s*\([一二三四五六七八九十]+\).+$"),
    re.compile(r"^\s*\d+(\.\d+)*[\.、]\s*.+$"),
]
SENTENCE_ENDINGS = "。！？!?；;：:"


@dataclass
class ParserContent:
    parser_name: str
    parser_dir: Path
    raw_text: str
    markdown_text: str
    cleaned_text: str
    blocks: list[str]
    page_count: int
    success: bool
    error_message: str


def normalize_whitespace(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t\u3000]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def normalize_for_compare(text: str) -> str:
    text = normalize_whitespace(text)
    text = re.sub(r"[ \t]+", "", text)
    return text


def split_blocks(text: str) -> list[str]:
    if not text:
        return []
    blocks = [normalize_whitespace(part) for part in re.split(r"\n\s*\n", text)]
    return [block for block in blocks if block]


def rouge_tokens(text: str) -> list[str]:
    normalized = normalize_for_compare(text)
    if not normalized:
        return []
    tokens = [token for token in re.split(r"[，。；：！？!?\n、,;:\s]+", normalized) if token]
    return tokens


def rouge_l_f1(prediction: str, reference: str) -> float | None:
    pred_tokens = rouge_tokens(prediction)
    ref_tokens = rouge_tokens(reference)
    if not pred_tokens or not ref_tokens:
        return None
    matcher = SequenceMatcher(a=pred_tokens, b=ref_tokens, autojunk=False)
    lcs = sum(block.size for block in matcher.get_matching_blocks())
    precision = lcs / len(pred_tokens) if pred_tokens else 0.0
    recall = lcs / len(ref_tokens) if ref_tokens else 0.0
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def load_json(path: Path) -> dict[str, Any]:
    import json

    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def load_parser_content(parser_name: str, parser_dir: Path, success: bool, error_message: str) -> ParserContent:
    parsed_md_path = parser_dir / "parsed.md"
    raw_path = parser_dir / "raw.txt"
    normalized_path = parser_dir / "normalized.json"

    markdown_text = parsed_md_path.read_text(encoding="utf-8") if parsed_md_path.exists() else ""
    raw_text = raw_path.read_text(encoding="utf-8") if raw_path.exists() else ""
    normalized = load_json(normalized_path)

    if not raw_text:
        raw_text = normalize_whitespace("\n\n".join(block.get("text", "") for block in normalized.get("blocks", []) if block.get("text")))
    if not markdown_text and parser_name in {"pymupdf4llm", "marker", "llamaparse"}:
        markdown_text = raw_text

    cleaned_text = normalize_whitespace(markdown_text or raw_text)
    normalized_blocks = normalized.get("blocks", [])
    blocks: list[str] = []
    if isinstance(normalized_blocks, list) and normalized_blocks:
        blocks = [
            normalize_whitespace(str(block.get("text", "")))
            for block in normalized_blocks
            if normalize_whitespace(str(block.get("text", "")))
        ]
    if not blocks:
        blocks = split_blocks(cleaned_text)

    pages = normalized.get("pages", [])
    page_count = len(pages) if isinstance(pages, list) and pages else 0
    return ParserContent(
        parser_name=parser_name,
        parser_dir=parser_dir,
        raw_text=raw_text,
        markdown_text=markdown_text,
        cleaned_text=cleaned_text,
        blocks=blocks,
        page_count=page_count,
        success=success,
        error_message=error_message,
    )


def detect_titles(text: str) -> int:
    count = 0
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if any(pattern.match(stripped) for pattern in TITLE_PATTERNS):
            count += 1
            continue
        if len(stripped) <= 20 and not re.search(r"[，。；：!?！？]", stripped):
            count += 1
    return count


def structure_metrics(content: ParserContent) -> dict[str, float | int | None]:
    blocks = content.blocks or split_blocks(content.cleaned_text)
    non_empty_blocks = [block for block in blocks if block.strip()]
    lines = [line.strip() for line in content.cleaned_text.splitlines() if line.strip()]

    avg_block_len = None
    if non_empty_blocks:
        avg_block_len = sum(len(block) for block in non_empty_blocks) / len(non_empty_blocks)

    short_line_ratio = None
    if lines:
        short_line_ratio = sum(1 for line in lines if len(line) <= 12) / len(lines)

    return {
        "title_count": detect_titles(content.cleaned_text),
        "block_count": len(non_empty_blocks),
        "avg_block_len": avg_block_len,
        "short_line_ratio": short_line_ratio,
    }


def table_metrics(content: ParserContent) -> dict[str, float | int | bool]:
    text = content.markdown_text or content.cleaned_text
    lines = [line for line in text.splitlines() if line.strip()]
    table_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.count("|") >= 3:
            table_lines.append(stripped)
            continue
        if "\t" in stripped:
            table_lines.append(stripped)
            continue
        if len(re.findall(r"\s{2,}", stripped)) >= 2 and len(stripped) >= 20:
            table_lines.append(stripped)

    total_text_len = max(len(text), 1)
    table_text_len = sum(len(line) for line in table_lines)
    return {
        "table_detected": bool(table_lines),
        "table_line_count": len(table_lines),
        "table_text_ratio": table_text_len / total_text_len,
    }


def rag_readiness_metrics(content: ParserContent) -> dict[str, float | None]:
    text = content.cleaned_text
    blocks = content.blocks or split_blocks(text)
    non_empty_blocks = [block for block in blocks if block.strip()]

    sentence_units = [segment.strip() for segment in re.split(r"[。！？!?；;\n]+", text) if segment.strip()]
    avg_sentence_len = None
    if sentence_units:
        avg_sentence_len = sum(len(unit) for unit in sentence_units) / len(sentence_units)

    candidate_sentences = [segment.strip() for segment in re.split(r"\n+", text) if segment.strip()]
    broken_sentence_ratio = None
    if candidate_sentences:
        broken_count = 0
        valid_count = 0
        for sentence in candidate_sentences:
            if len(sentence) < 8:
                continue
            valid_count += 1
            if sentence[-1] not in SENTENCE_ENDINGS and "|" not in sentence and "\t" not in sentence:
                broken_count += 1
        broken_sentence_ratio = (broken_count / valid_count) if valid_count else 0.0

    long_block_ratio = None
    empty_block_ratio = None
    if blocks:
        long_block_ratio = sum(1 for block in blocks if len(block) > 1000) / len(blocks)
        empty_block_ratio = sum(1 for block in blocks if not block.strip()) / len(blocks)
    elif text:
        long_block_ratio = 1.0 if len(text) > 1000 else 0.0
        empty_block_ratio = 0.0

    return {
        "avg_sentence_len": avg_sentence_len,
        "broken_sentence_ratio": broken_sentence_ratio,
        "long_block_ratio": long_block_ratio,
        "empty_block_ratio": empty_block_ratio,
    }
