from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List

__all__ = ["load_pdf", "load_docx"]

PageRecord = Dict[str, object]

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_MINERU_BIN = _PROJECT_ROOT / ".venv" / "bin" / "mineru"


def _ensure_input_path(path: str | Path, allowed_suffixes: tuple[str, ...]) -> Path:
    input_path = Path(path)
    if not input_path.is_file():
        raise FileNotFoundError(f"文件未找到: {input_path}")
    if input_path.suffix.lower() not in allowed_suffixes:
        raise ValueError(f"不支持的文件类型: {input_path.suffix}")
    return input_path


def _resolve_mineru_bin() -> str:
    configured = os.environ.get("MINERU_BIN")
    if configured:
        return configured
    if _DEFAULT_MINERU_BIN.exists():
        return str(_DEFAULT_MINERU_BIN)
    return "mineru"


def _prepare_env() -> dict[str, str]:
    env = os.environ.copy()
    env["MINERU_MODEL_SOURCE"] = "local"

    no_proxy_items = {"127.0.0.1", "localhost"}
    existing = env.get("NO_PROXY", "") or env.get("no_proxy", "")
    if existing:
        no_proxy_items.update(item.strip() for item in existing.split(",") if item.strip())
    no_proxy_value = ",".join(sorted(no_proxy_items))
    env["NO_PROXY"] = no_proxy_value
    env["no_proxy"] = no_proxy_value
    return env


def _expected_parse_dir(output_root: Path, input_path: Path) -> Path:
    # pdf 走 hybrid_auto-engine 默认会输出到 hybrid_auto
    # docx 在 MinerU 中固定输出到 office
    parse_dir_name = "office" if input_path.suffix.lower() == ".docx" else "hybrid_auto"
    return output_root / input_path.stem / parse_dir_name


def _locate_markdown_file(parse_dir: Path, stem: str) -> Path:
    exact_match = parse_dir / f"{stem}.md"
    if exact_match.exists():
        return exact_match

    candidates = sorted(parse_dir.glob("*.md"))
    if candidates:
        return candidates[0]

    # 兼容 MinerU 未来目录结构变化
    deep_candidates = sorted(parse_dir.rglob("*.md"))
    if deep_candidates:
        return deep_candidates[0]

    raise FileNotFoundError(f"未在 MinerU 输出目录中找到 markdown: {parse_dir}")


def _run_mineru_and_read_markdown(input_path: Path) -> str:
    mineru_bin = _resolve_mineru_bin()
    env = _prepare_env()

    tmp_parent = _PROJECT_ROOT / "data" / ".mineru_tmp"
    tmp_parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="mineru_parse_", dir=tmp_parent) as temp_dir:
        output_root = Path(temp_dir)
        command = [
            mineru_bin,
            "-p",
            str(input_path),
            "-o",
            str(output_root),
            "-b",
            "hybrid-auto-engine",
            "-m",
            "auto",
        ]

        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
        if completed.returncode != 0:
            stderr_tail = (completed.stderr or "").strip()[-1200:]
            raise RuntimeError(
                f"MinerU 解析失败(return code={completed.returncode})，错误信息:\n{stderr_tail}"
            )

        parse_dir = _expected_parse_dir(output_root, input_path)
        md_path = _locate_markdown_file(parse_dir, input_path.stem)
        markdown_text = md_path.read_text(encoding="utf-8").strip()
        if not markdown_text:
            raise RuntimeError(f"MinerU 输出为空: {md_path}")
        return markdown_text


def _to_page_records(input_path: Path, markdown_text: str) -> List[PageRecord]:
    # 当前流程按文档级返回，后续 chunker 仍可按 Markdown 标题进一步切分。
    return [
        {
            "doc_name": input_path.name,
            "page": 1,
            "text": markdown_text,
            "section_path": None,
        }
    ]


def load_pdf(path: str | Path) -> List[PageRecord]:
    pdf_path = _ensure_input_path(path, (".pdf",))
    markdown_text = _run_mineru_and_read_markdown(pdf_path)
    return _to_page_records(pdf_path, markdown_text)


def load_docx(path: str | Path) -> List[PageRecord]:
    docx_path = _ensure_input_path(path, (".docx",))
    markdown_text = _run_mineru_and_read_markdown(docx_path)
    return _to_page_records(docx_path, markdown_text)
