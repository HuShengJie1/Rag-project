from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
EXP_ROOT = Path(__file__).resolve().parents[1]
SRC = EXP_ROOT / "src"
sys.path.insert(0, str(SRC))

from evaluation import GroundTruthRegistry
from evaluation.parser_metrics import (
    ParserContent,
    load_parser_content,
    normalize_whitespace,
    rag_readiness_metrics,
    rouge_l_f1,
    structure_metrics,
    table_metrics,
)
from utils.logging import get_logger


@dataclass
class EvalResult:
    doc_id: str
    parser_name: str
    success: bool
    error_message: str
    rouge_l: float | None
    coverage_rate: float | None
    text_length: int
    title_count: int | None
    block_count: int | None
    avg_block_len: float | None
    short_line_ratio: float | None
    table_detected: bool | None
    table_line_count: int | None
    table_text_ratio: float | None
    avg_sentence_len: float | None
    broken_sentence_ratio: float | None
    long_block_ratio: float | None
    empty_block_ratio: float | None

    def to_row(self) -> dict[str, Any]:
        return self.__dict__


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate parsing outputs for engineering certification documents.")
    parser.add_argument("--manifest", type=str, default="experiments/parsing_eval/manifest.csv")
    parser.add_argument("--subset", type=str, default="experiments/parsing_eval/phase1_subset.csv")
    parser.add_argument("--gt-manifest", type=str, default="experiments/parsing_eval/ground_truth/gt_manifest.csv")
    parser.add_argument("--output-dir", type=str, default="experiments/outputs/parsing_eval")
    return parser.parse_args()


def get_parser_names(columns: list[str]) -> list[str]:
    parser_names: list[str] = []
    for column in columns:
        if not column.endswith("_output"):
            continue
        parser_name = column[: -len("_output")]
        if parser_name != "source_pdf":
            parser_names.append(parser_name)
    return parser_names


def safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def load_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str).fillna("")


def compute_text_metrics(content: ParserContent, gt_text: str | None) -> tuple[float | None, float | None]:
    if not gt_text:
        return None, None
    rouge = rouge_l_f1(content.cleaned_text, gt_text)
    gt_len = len(gt_text)
    coverage = len(content.cleaned_text) / max(gt_len, 1)
    return rouge, coverage


def evaluate_parser_output(
    doc_id: str,
    parser_name: str,
    parser_dir: Path | None,
    parser_status: str,
    parser_error: str,
    gt_text: str | None,
) -> EvalResult:
    success = parser_status == "success" and parser_dir is not None and parser_dir.exists()
    content = ParserContent(
        parser_name=parser_name,
        parser_dir=parser_dir or Path("."),
        raw_text="",
        markdown_text="",
        cleaned_text="",
        blocks=[],
        page_count=0,
        success=success,
        error_message=parser_error,
    )

    if parser_dir and parser_dir.exists():
        content = load_parser_content(
            parser_name=parser_name,
            parser_dir=parser_dir,
            success=success,
            error_message=parser_error,
        )

    rouge_l, coverage_rate = compute_text_metrics(content, gt_text)
    structure = structure_metrics(content)
    table = table_metrics(content)
    rag = rag_readiness_metrics(content)

    return EvalResult(
        doc_id=doc_id,
        parser_name=parser_name,
        success=success,
        error_message=content.error_message or parser_error,
        rouge_l=rouge_l,
        coverage_rate=coverage_rate,
        text_length=len(content.cleaned_text),
        title_count=structure["title_count"],
        block_count=structure["block_count"],
        avg_block_len=structure["avg_block_len"],
        short_line_ratio=structure["short_line_ratio"],
        table_detected=table["table_detected"],
        table_line_count=table["table_line_count"],
        table_text_ratio=table["table_text_ratio"],
        avg_sentence_len=rag["avg_sentence_len"],
        broken_sentence_ratio=rag["broken_sentence_ratio"],
        long_block_ratio=rag["long_block_ratio"],
        empty_block_ratio=rag["empty_block_ratio"],
    )


def build_summary(results_df: pd.DataFrame) -> pd.DataFrame:
    numeric_columns = [
        "rouge_l",
        "coverage_rate",
        "text_length",
        "title_count",
        "block_count",
        "avg_block_len",
        "short_line_ratio",
        "table_line_count",
        "table_text_ratio",
        "avg_sentence_len",
        "broken_sentence_ratio",
        "long_block_ratio",
        "empty_block_ratio",
    ]

    df = results_df.copy()
    for column in numeric_columns:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    df["success_int"] = df["success"].astype(int)
    df["has_gt"] = df["rouge_l"].notna().astype(int)
    df["table_detected_int"] = df["table_detected"].astype(str).str.lower().eq("true").astype(int)

    grouped = df.groupby("parser_name", as_index=False).agg(
        doc_count=("doc_id", "count"),
        success_count=("success_int", "sum"),
        gt_doc_count=("has_gt", "sum"),
        rouge_l=("rouge_l", "mean"),
        coverage_rate=("coverage_rate", "mean"),
        text_length=("text_length", "mean"),
        title_count=("title_count", "mean"),
        block_count=("block_count", "mean"),
        avg_block_len=("avg_block_len", "mean"),
        short_line_ratio=("short_line_ratio", "mean"),
        table_detected_rate=("table_detected_int", "mean"),
        table_line_count=("table_line_count", "mean"),
        table_text_ratio=("table_text_ratio", "mean"),
        avg_sentence_len=("avg_sentence_len", "mean"),
        broken_sentence_ratio=("broken_sentence_ratio", "mean"),
        long_block_ratio=("long_block_ratio", "mean"),
        empty_block_ratio=("empty_block_ratio", "mean"),
    )
    return grouped.sort_values(["rouge_l", "success_count"], ascending=[False, False])


def build_report(results_df: pd.DataFrame, summary_df: pd.DataFrame, missing_gt_doc_ids: list[str]) -> str:
    lines: list[str] = []
    lines.append("# Parser Eval Report")
    lines.append("")
    lines.append(f"- Evaluated docs: {results_df['doc_id'].nunique()}")
    lines.append(f"- Parsers: {results_df['parser_name'].nunique()}")
    lines.append(f"- Rows: {len(results_df)}")
    lines.append(f"- Docs without GT: {len(missing_gt_doc_ids)}")
    lines.append("")
    lines.append("## Parser Summary")
    lines.append("")
    lines.append("| parser | docs | success | gt_docs | rouge_l | coverage_rate | table_detected_rate | broken_sentence_ratio |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for _, row in summary_df.iterrows():
        lines.append(
            "| {parser_name} | {doc_count} | {success_count} | {gt_doc_count} | {rouge_l:.4f} | {coverage_rate:.4f} | {table_detected_rate:.4f} | {broken_sentence_ratio:.4f} |".format(
                parser_name=row["parser_name"],
                doc_count=int(row["doc_count"]),
                success_count=int(row["success_count"]),
                gt_doc_count=int(row["gt_doc_count"]),
                rouge_l=(row["rouge_l"] if pd.notna(row["rouge_l"]) else 0.0),
                coverage_rate=(row["coverage_rate"] if pd.notna(row["coverage_rate"]) else 0.0),
                table_detected_rate=(row["table_detected_rate"] if pd.notna(row["table_detected_rate"]) else 0.0),
                broken_sentence_ratio=(row["broken_sentence_ratio"] if pd.notna(row["broken_sentence_ratio"]) else 0.0),
            )
        )

    lines.append("")
    lines.append("## Missing GT")
    if missing_gt_doc_ids:
        for doc_id in missing_gt_doc_ids:
            lines.append(f"- {doc_id}")
    else:
        lines.append("- None")

    lines.append("")
    lines.append("## Notes")
    lines.append("- ROUGE-L and coverage_rate are only computed for docs with GT.")
    lines.append("- Structural, table, and RAG-readiness metrics are computed from parser outputs regardless of GT availability.")
    lines.append("- Failures remain in the result table and do not interrupt the overall experiment.")
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    manifest_path = (REPO_ROOT / args.manifest).resolve()
    subset_path = (REPO_ROOT / args.subset).resolve()
    gt_manifest_path = (REPO_ROOT / args.gt_manifest).resolve()
    output_dir = (REPO_ROOT / args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    logger = get_logger("parser_eval", EXP_ROOT / "outputs" / "logs" / "parser_eval.log")
    logger.info("Loading manifest=%s subset=%s gt_manifest=%s", manifest_path, subset_path, gt_manifest_path)

    manifest_df = load_csv(manifest_path)
    subset_df = load_csv(subset_path)
    selected_doc_ids = [str(doc_id).strip() for doc_id in subset_df["doc_id"].tolist() if str(doc_id).strip()]
    parser_names = get_parser_names(list(manifest_df.columns))
    manifest_by_doc = {str(row["doc_id"]).strip(): row for _, row in manifest_df.iterrows()}
    gt_registry = GroundTruthRegistry.from_manifest(gt_manifest_path)

    results: list[dict[str, Any]] = []
    missing_gt_doc_ids: set[str] = set()

    for doc_id in selected_doc_ids:
        manifest_row = manifest_by_doc.get(doc_id)
        if manifest_row is None:
            logger.warning("doc_id=%s not found in manifest", doc_id)
            continue

        gt_text = gt_registry.read_text(doc_id)
        if gt_text is not None:
            gt_text = normalize_whitespace(gt_text)
        else:
            missing_gt_doc_ids.add(doc_id)

        for parser_name in parser_names:
            try:
                output_rel = str(manifest_row.get(f"{parser_name}_output", "")).strip()
                parser_status = str(manifest_row.get(f"{parser_name}_status", "")).strip().lower()
                parser_error = str(manifest_row.get(f"{parser_name}_error", "")).strip()
                parser_dir = (EXP_ROOT / "parsing_eval" / Path(output_rel)).resolve() if output_rel else None

                result = evaluate_parser_output(
                    doc_id=doc_id,
                    parser_name=parser_name,
                    parser_dir=parser_dir,
                    parser_status=parser_status,
                    parser_error=parser_error,
                    gt_text=gt_text,
                )
                results.append(result.to_row())
            except Exception as exc:
                logger.exception("Failed evaluating doc_id=%s parser=%s", doc_id, parser_name)
                results.append(
                    EvalResult(
                        doc_id=doc_id,
                        parser_name=parser_name,
                        success=False,
                        error_message=str(exc),
                        rouge_l=None,
                        coverage_rate=None,
                        text_length=0,
                        title_count=None,
                        block_count=None,
                        avg_block_len=None,
                        short_line_ratio=None,
                        table_detected=None,
                        table_line_count=None,
                        table_text_ratio=None,
                        avg_sentence_len=None,
                        broken_sentence_ratio=None,
                        long_block_ratio=None,
                        empty_block_ratio=None,
                    ).to_row()
                )

    results_df = pd.DataFrame(results)
    if not results_df.empty:
        bool_columns = ["success", "table_detected"]
        for column in bool_columns:
            if column in results_df.columns:
                results_df[column] = results_df[column].astype("boolean")

    parser_results_path = output_dir / "parser_results.csv"
    parser_summary_path = output_dir / "parser_results_summary.csv"
    parser_report_path = output_dir / "parser_eval_report.md"

    results_df.to_csv(parser_results_path, index=False, encoding="utf-8-sig")
    summary_df = build_summary(results_df) if not results_df.empty else pd.DataFrame()
    summary_df.to_csv(parser_summary_path, index=False, encoding="utf-8-sig")
    parser_report_path.write_text(
        build_report(results_df, summary_df, sorted(missing_gt_doc_ids, key=lambda x: (len(x), x))),
        encoding="utf-8",
    )
    logger.info("Saved parser evaluation results to %s", output_dir)


if __name__ == "__main__":
    main()
