from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


TITLE_PATTERNS = [
    re.compile(r"^\s{0,3}#{1,6}\s+.+$"),
    re.compile(r"^\s*[一二三四五六七八九十]+、.+$"),
    re.compile(r"^\s*第[一二三四五六七八九十百]+[章节部分].+$"),
    re.compile(r"^\s*（[一二三四五六七八九十]+）.+$"),
    re.compile(r"^\s*\([一二三四五六七八九十]+\).+$"),
    re.compile(r"^\s*\d+(\.\d+){0,3}[\.、]\s*.+$"),
]
LIST_PATTERNS = [
    re.compile(r"^\s*[-*+•·]\s+.+$"),
    re.compile(r"^\s*\d+[\.\)]\s+.+$"),
    re.compile(r"^\s*[（(]?\d+[）)]\s*.+$"),
]
HTML_TAG_RE = re.compile(r"<[^>]+>")
HTML_HEADING_RE = re.compile(r"<h[1-6][^>]*>.*?</h[1-6]>", re.IGNORECASE)
HTML_TABLE_RE = re.compile(r"</?(?:table|tr|td|th)\b[^>]*>", re.IGNORECASE)
HTML_TABLE_TAG_RE = re.compile(r"</?(?:table|tr)\b[^>]*>", re.IGNORECASE)
HTML_TD_RE = re.compile(r"</?td\b[^>]*>", re.IGNORECASE)
HTML_TH_RE = re.compile(r"</?th\b[^>]*>", re.IGNORECASE)
TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?(?:\s*:?-{3,}:?\s*\|){2,}\s*:?-{3,}:?\s*\|?\s*$")
SENTENCE_ENDINGS = "。！？!?；;：:"
SENTENCE_END_RE = re.compile(rf"[{re.escape(SENTENCE_ENDINGS)}][\"'”’）】\]]*$")
PAGE_FOOTER_RE = re.compile(r"^\s*(?:第?\s*\d+\s*页|\d+\s*/\s*\d+|\d+)\s*$")


@dataclass
class ParserContentV2:
    parser_name: str
    parser_dir: Path
    raw_text: str
    markdown_text: str
    cleaned_text: str
    blocks: list[str]
    normalized: dict[str, Any]
    success: bool
    error_message: str


def normalize_whitespace(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t\u3000]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def strip_html(text: str) -> str:
    return normalize_whitespace(HTML_TAG_RE.sub("", text or ""))


def split_blocks(text: str) -> list[str]:
    if not text:
        return []
    blocks = [normalize_whitespace(chunk) for chunk in re.split(r"\n\s*\n", text)]
    return [block for block in blocks if block]


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def load_parser_content_v2(parser_name: str, parser_dir: Path, success: bool, error_message: str) -> ParserContentV2:
    raw_path = parser_dir / "raw.txt"
    md_path = parser_dir / "parsed.md"
    normalized_path = parser_dir / "normalized.json"

    raw_text = raw_path.read_text(encoding="utf-8") if raw_path.exists() else ""
    markdown_text = md_path.read_text(encoding="utf-8") if md_path.exists() else ""
    normalized = load_json(normalized_path)

    if not raw_text:
        raw_text = normalize_whitespace(
            "\n\n".join(
                str(block.get("text", ""))
                for block in normalized.get("blocks", [])
                if isinstance(block, dict) and str(block.get("text", "")).strip()
            )
        )
    if not markdown_text and parser_name in {"marker", "pymupdf4llm", "llamaparse"}:
        markdown_text = raw_text

    cleaned_text = normalize_whitespace(markdown_text or raw_text)
    normalized_blocks = normalized.get("blocks", [])
    blocks: list[str] = []
    if isinstance(normalized_blocks, list):
        blocks = [
            normalize_whitespace(str(block.get("text", "")))
            for block in normalized_blocks
            if isinstance(block, dict) and normalize_whitespace(str(block.get("text", "")))
        ]
    if not blocks:
        blocks = split_blocks(cleaned_text)

    return ParserContentV2(
        parser_name=parser_name,
        parser_dir=parser_dir,
        raw_text=raw_text,
        markdown_text=markdown_text,
        cleaned_text=cleaned_text,
        blocks=blocks,
        normalized=normalized,
        success=success,
        error_message=error_message,
    )


def safe_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


def bounded_score(value: float | None, ideal_low: float, ideal_high: float, outer_low: float, outer_high: float) -> float | None:
    if value is None or np.isnan(value):
        return None
    if value < outer_low or value > outer_high:
        return 0.0
    if ideal_low <= value <= ideal_high:
        return 1.0
    if value < ideal_low:
        return float((value - outer_low) / max(ideal_low - outer_low, 1e-6))
    return float((outer_high - value) / max(outer_high - ideal_high, 1e-6))


def descending_score(value: float | None, good_threshold: float, bad_threshold: float) -> float | None:
    if value is None or np.isnan(value):
        return None
    if value <= good_threshold:
        return 1.0
    if value >= bad_threshold:
        return 0.0
    return float((bad_threshold - value) / max(bad_threshold - good_threshold, 1e-6))


def saturating_score(value: float | None, full_score_at: float) -> float | None:
    if value is None or np.isnan(value):
        return None
    if full_score_at <= 0:
        return 1.0 if value > 0 else 0.0
    return float(max(0.0, min(value / full_score_at, 1.0)))


def weighted_mean(pairs: list[tuple[float | None, float]]) -> float | None:
    valid = [(value, weight) for value, weight in pairs if value is not None and not np.isnan(value)]
    if not valid:
        return None
    total_weight = sum(weight for _, weight in valid)
    if total_weight <= 0:
        return None
    return float(sum(value * weight for value, weight in valid) / total_weight)


def is_title_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if HTML_HEADING_RE.search(stripped):
        return True
    if any(pattern.match(stripped) for pattern in TITLE_PATTERNS):
        return True
    plain = strip_html(stripped)
    if len(plain) <= 24 and plain and not re.search(r"[，。；：!?！？]", plain):
        return True
    return False


def is_list_item(line: str) -> bool:
    stripped = strip_html(line)
    return any(pattern.match(stripped) for pattern in LIST_PATTERNS)


def line_alignment_columns(line: str) -> int:
    stripped = strip_html(line)
    if not stripped:
        return 0
    return len([part for part in re.split(r"\s{2,}", stripped) if part.strip()])


def is_markdown_table_line(line: str) -> bool:
    stripped = line.strip()
    if stripped.count("|") >= 3:
        return True
    if TABLE_SEPARATOR_RE.match(stripped):
        return True
    return False


def is_tabular_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if is_markdown_table_line(stripped):
        return True
    if "\t" in stripped and len([part for part in stripped.split("\t") if part.strip()]) >= 2:
        return True
    if HTML_TABLE_RE.search(stripped):
        return True
    if line_alignment_columns(stripped) >= 3 and len(strip_html(stripped)) >= 20:
        return True
    return False


def extract_lines(content: ParserContentV2) -> list[str]:
    return [line.rstrip() for line in (content.markdown_text or content.raw_text or content.cleaned_text).splitlines()]


def count_title_lines(lines: list[str], normalized: dict[str, Any]) -> int:
    rule_count = sum(1 for line in lines if is_title_line(line))
    block_count = 0
    for block in normalized.get("blocks", []):
        if not isinstance(block, dict):
            continue
        block_type = str(block.get("block_type", "")).lower()
        if block_type in {"heading", "sectionheader", "title"}:
            block_count += 1
    return max(rule_count, block_count)


def enhanced_structure_metrics(content: ParserContentV2) -> dict[str, float | int | None]:
    lines = [line.strip() for line in extract_lines(content) if line.strip()]
    plain_lines = [strip_html(line) for line in lines if strip_html(line)]
    blocks = [block for block in content.blocks if block.strip()]

    title_count = count_title_lines(lines, content.normalized)
    block_count = len(blocks)
    avg_block_len = float(np.mean([len(block) for block in blocks])) if blocks else None
    short_line_ratio = float(np.mean([len(line) <= 12 for line in plain_lines])) if plain_lines else None
    long_line_ratio = float(np.mean([len(line) >= 160 for line in plain_lines])) if plain_lines else None

    title_density = title_count / max(len(plain_lines), 1)
    text_length = max(len(content.cleaned_text), 1)
    block_density = block_count / max(text_length / 1000.0, 1e-6)

    structure_score = weighted_mean(
        [
            (bounded_score(title_density, 0.015, 0.18, 0.0, 0.40), 0.22),
            (bounded_score(block_density, 0.8, 10.0, 0.05, 24.0), 0.23),
            (bounded_score(avg_block_len, 120.0, 700.0, 40.0, 1800.0), 0.25),
            (descending_score(short_line_ratio, 0.20, 0.75), 0.20),
            (descending_score(long_line_ratio, 0.08, 0.45), 0.10),
        ]
    )

    return {
        "title_count": title_count,
        "block_count": block_count,
        "avg_block_len": avg_block_len,
        "short_line_ratio": short_line_ratio,
        "long_line_ratio_lines": long_line_ratio,
        "structure_score": structure_score,
    }


def enhanced_table_metrics(content: ParserContentV2, table_expected: bool | None) -> dict[str, float | int | bool | None]:
    source_text = content.markdown_text or content.raw_text or content.cleaned_text
    lines = [line for line in source_text.splitlines() if line.strip()]

    markdown_table_lines = [line for line in lines if is_markdown_table_line(line)]
    tab_table_lines = [line for line in lines if ("\t" in line and len([part for part in line.split("\t") if part.strip()]) >= 2)]
    aligned_table_lines = [
        line
        for line in lines
        if line not in markdown_table_lines and line_alignment_columns(line) >= 3 and len(strip_html(line)) >= 20
    ]
    html_table_lines = [line for line in lines if HTML_TABLE_RE.search(line)]

    html_table_tag_count = len(HTML_TABLE_TAG_RE.findall(source_text))
    html_td_count = len(HTML_TD_RE.findall(source_text))
    html_th_count = len(HTML_TH_RE.findall(source_text))

    table_line_pool: list[str] = []
    seen: set[str] = set()
    for line in markdown_table_lines + tab_table_lines + aligned_table_lines + html_table_lines:
        key = line.strip()
        if key and key not in seen:
            table_line_pool.append(line)
            seen.add(key)

    table_line_count = len(table_line_pool)
    total_text_len = max(len(source_text), 1)
    table_text_ratio = sum(len(line) for line in table_line_pool) / total_text_len if table_line_pool else 0.0
    signal_type_count = sum(
        [
            bool(markdown_table_lines),
            bool(tab_table_lines),
            bool(aligned_table_lines),
            bool(html_table_tag_count or html_td_count or html_th_count),
        ]
    )
    table_detected = bool(table_line_pool or html_table_tag_count or html_td_count or html_th_count)

    html_signal_score = saturating_score(
        html_table_tag_count + 0.35 * html_td_count + 0.35 * html_th_count,
        full_score_at=8.0,
    )
    base_table_score = weighted_mean(
        [
            (1.0 if table_detected else 0.0, 0.28),
            (saturating_score(float(table_line_count), 10.0), 0.22),
            (saturating_score(table_text_ratio, 0.15), 0.20),
            (saturating_score(float(signal_type_count), 3.0), 0.10),
            (html_signal_score, 0.20),
        ]
    )

    table_score: float | None
    if table_expected is False:
        table_score = None
    else:
        table_score = base_table_score
        if html_signal_score is not None and html_signal_score > 0:
            table_score = min(1.0, (table_score or 0.0) + 0.18 * html_signal_score)

    return {
        "table_detected": table_detected,
        "table_line_count": table_line_count,
        "table_text_ratio": table_text_ratio,
        "html_table_tag_count": html_table_tag_count,
        "html_td_count": html_td_count,
        "html_th_count": html_th_count,
        "table_score": table_score,
    }


def repeated_short_lines(lines: list[str]) -> Counter[str]:
    normalized = [strip_html(line) for line in lines if 4 <= len(strip_html(line)) <= 40]
    return Counter(normalized)


def is_header_footer_line(line: str, repeated: Counter[str]) -> bool:
    plain = strip_html(line)
    if not plain:
        return False
    if PAGE_FOOTER_RE.match(plain):
        return True
    if repeated.get(plain, 0) >= 2 and len(plain) <= 35:
        return True
    if len(plain) <= 10 and re.fullmatch(r"[\d\-/:年月日 ]+", plain):
        return True
    return False


def is_body_candidate_line(line: str, repeated: Counter[str]) -> bool:
    plain = strip_html(line)
    if not plain:
        return False
    if len(plain) < 12:
        return False
    if is_title_line(line):
        return False
    if is_list_item(line):
        return False
    if is_tabular_line(line):
        return False
    if is_header_footer_line(line, repeated):
        return False
    if not re.search(r"[\u4e00-\u9fffA-Za-z]", plain):
        return False
    return True


def build_body_paragraphs(content: ParserContentV2) -> list[str]:
    lines = extract_lines(content)
    repeated = repeated_short_lines(lines)
    paragraphs: list[str] = []
    current: list[str] = []

    def flush() -> None:
        if not current:
            return
        paragraph = normalize_whitespace(" ".join(current))
        if paragraph:
            paragraphs.append(paragraph)
        current.clear()

    for raw_line in lines:
        if not raw_line.strip():
            flush()
            continue
        if not is_body_candidate_line(raw_line, repeated):
            flush()
            continue
        current.append(strip_html(raw_line))
    flush()
    return paragraphs


def split_sentences_from_paragraphs(paragraphs: list[str]) -> list[str]:
    sentences: list[str] = []
    for paragraph in paragraphs:
        for part in re.split(r"[。！？!?；;]+", paragraph):
            normalized = normalize_whitespace(part)
            if len(normalized) >= 8:
                sentences.append(normalized)
    return sentences


def recomputed_rag_metrics(content: ParserContentV2) -> dict[str, float | None]:
    blocks = content.blocks or split_blocks(content.cleaned_text)
    total_blocks = len(blocks)
    non_empty_blocks = [block for block in blocks if block.strip()]

    body_paragraphs = build_body_paragraphs(content)
    body_sentences = split_sentences_from_paragraphs(body_paragraphs)

    avg_sentence_len = float(np.mean([len(sentence) for sentence in body_sentences])) if body_sentences else None

    candidate_paragraphs = [paragraph for paragraph in body_paragraphs if len(paragraph) >= 20]
    broken_sentence_ratio = None
    if candidate_paragraphs:
        broken_count = sum(1 for paragraph in candidate_paragraphs if not SENTENCE_END_RE.search(paragraph))
        broken_sentence_ratio = broken_count / len(candidate_paragraphs)

    long_block_ratio = None
    empty_block_ratio = None
    if total_blocks > 0:
        long_block_ratio = sum(1 for block in blocks if len(block) > 1000) / total_blocks
        empty_block_ratio = sum(1 for block in blocks if not block.strip()) / total_blocks
    elif content.cleaned_text:
        long_block_ratio = 1.0 if len(content.cleaned_text) > 1000 else 0.0
        empty_block_ratio = 0.0

    non_empty_score = weighted_mean(
        [
            (1.0 if content.cleaned_text.strip() else 0.0, 0.6),
            (1.0 - (empty_block_ratio or 0.0) if empty_block_ratio is not None else None, 0.4),
        ]
    )
    rag_readiness_score = weighted_mean(
        [
            (non_empty_score, 0.20),
            (bounded_score(avg_sentence_len, 18.0, 60.0, 8.0, 120.0), 0.20),
            (descending_score(broken_sentence_ratio, 0.12, 0.85), 0.30),
            (descending_score(long_block_ratio, 0.12, 0.85), 0.20),
            (descending_score(empty_block_ratio, 0.05, 0.60), 0.10),
        ]
    )

    return {
        "avg_sentence_len": avg_sentence_len,
        "broken_sentence_ratio_recomputed": broken_sentence_ratio,
        "long_block_ratio": long_block_ratio,
        "empty_block_ratio": empty_block_ratio,
        "rag_readiness_score": rag_readiness_score,
    }


def symmetric_coverage_score(coverage_rate: float | None) -> float | None:
    if coverage_rate is None or np.isnan(coverage_rate) or coverage_rate <= 0:
        return None
    return float(min(coverage_rate, 1.0 / max(coverage_rate, 1e-6)))


def final_score_v2(
    rouge_l: float | None,
    coverage_score: float | None,
    structure_score: float | None,
    table_score: float | None,
    rag_readiness_score: float | None,
) -> float | None:
    return weighted_mean(
        [
            (rouge_l, 0.15),
            (coverage_score, 0.10),
            (structure_score, 0.25),
            (table_score, 0.25),
            (rag_readiness_score, 0.25),
        ]
    )
