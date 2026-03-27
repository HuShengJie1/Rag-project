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

from evaluation.parser_metrics_v2 import (
    enhanced_structure_metrics,
    enhanced_table_metrics,
    final_score_v2,
    load_parser_content_v2,
    recomputed_rag_metrics,
    safe_float,
    symmetric_coverage_score,
)
from utils.logging import get_logger


@dataclass
class EvalResultV2:
    doc_id: str
    doc_type: str
    table_expected: str
    parser_name: str
    success: bool
    error_message: str
    rouge_l: float | None
    coverage_rate: float | None
    coverage_score: float | None
    title_count: int | None
    block_count: int | None
    avg_block_len: float | None
    short_line_ratio: float | None
    table_detected: bool | None
    table_line_count: int | None
    table_text_ratio: float | None
    html_table_tag_count: int | None
    html_td_count: int | None
    html_th_count: int | None
    table_score: float | None
    avg_sentence_len: float | None
    broken_sentence_ratio_recomputed: float | None
    long_block_ratio: float | None
    empty_block_ratio: float | None
    structure_score: float | None
    rag_readiness_score: float | None
    final_score_v2: float | None

    def to_row(self) -> dict[str, Any]:
        return self.__dict__


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Recompute parser evaluation with a fairer V2 scoring system.")
    parser.add_argument("--results", type=str, default="experiments/outputs/parsing_eval/parser_results.csv")
    parser.add_argument("--manifest", type=str, default="experiments/parsing_eval/manifest.csv")
    parser.add_argument("--subset", type=str, default="experiments/parsing_eval/phase1_subset.csv")
    parser.add_argument("--output-dir", type=str, default="experiments/outputs/parsing_eval")
    return parser.parse_args()


def load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str).fillna("")


def as_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def get_doc_type(doc_id: str, subset_by_doc: dict[str, dict[str, str]], manifest_by_doc: dict[str, dict[str, str]]) -> str:
    subset_row = subset_by_doc.get(doc_id, {})
    for key in ("doc_type_inferred", "doc_type_raw"):
        value = subset_row.get(key, "").strip()
        if value:
            return value
    return manifest_by_doc.get(doc_id, {}).get("doc_type", "").strip()


def infer_table_expected(doc_id: str, doc_type: str, subset_by_doc: dict[str, dict[str, str]]) -> bool | None:
    subset_row = subset_by_doc.get(doc_id, {})
    raw_flag = subset_row.get("table_rich", "").strip().lower()
    if raw_flag in {"yes", "true", "1"}:
        return True
    if raw_flag in {"no", "false", "0"}:
        return False

    lowered = doc_type.lower()
    if any(token in lowered for token in ["attainment", "training_program", "syllabus", "handbook"]):
        return True
    if any(token in doc_type for token in ["达成", "培养方案", "课程教学大纲", "手册", "支撑矩阵", "评价"]):
        return True
    if any(token in lowered for token in ["policy", "quality_report"]):
        return None
    return None


def resolve_parser_dir(
    doc_id: str,
    parser_name: str,
    manifest_by_doc: dict[str, dict[str, str]],
    manifest_root: Path,
) -> tuple[Path | None, str, str]:
    row = manifest_by_doc.get(doc_id)
    if not row:
        return None, "", f"doc_id {doc_id} not found in manifest"
    output_key = f"{parser_name}_output"
    status_key = f"{parser_name}_status"
    error_key = f"{parser_name}_error"
    output_rel = row.get(output_key, "").strip()
    status = row.get(status_key, "").strip()
    error = row.get(error_key, "").strip()
    if not output_rel:
        return None, status, error or "missing parser output path"
    parser_dir = (manifest_root / output_rel).resolve()
    return parser_dir, status, error


def build_summary(results_df: pd.DataFrame) -> pd.DataFrame:
    df = results_df.copy()
    numeric_columns = [
        "rouge_l",
        "coverage_rate",
        "coverage_score",
        "title_count",
        "block_count",
        "avg_block_len",
        "short_line_ratio",
        "table_line_count",
        "table_text_ratio",
        "html_table_tag_count",
        "html_td_count",
        "html_th_count",
        "table_score",
        "avg_sentence_len",
        "broken_sentence_ratio_recomputed",
        "long_block_ratio",
        "empty_block_ratio",
        "structure_score",
        "rag_readiness_score",
        "final_score_v2",
    ]
    for column in numeric_columns:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    df["success_int"] = df["success"].astype(str).str.lower().eq("true").astype(int)
    df["table_detected_int"] = df["table_detected"].astype(str).str.lower().eq("true").astype(int)
    df["table_applicable_int"] = df["table_score"].notna().astype(int)
    df["has_gt_int"] = df["rouge_l"].notna().astype(int)

    summary = (
        df.groupby("parser_name", as_index=False)
        .agg(
            sample_count=("doc_id", "count"),
            success_count=("success_int", "sum"),
            gt_doc_count=("has_gt_int", "sum"),
            table_applicable_count=("table_applicable_int", "sum"),
            final_score_v2_mean=("final_score_v2", "mean"),
            rouge_l_mean=("rouge_l", "mean"),
            coverage_score_mean=("coverage_score", "mean"),
            structure_score_mean=("structure_score", "mean"),
            table_score_mean=("table_score", "mean"),
            rag_readiness_score_mean=("rag_readiness_score", "mean"),
            title_count_mean=("title_count", "mean"),
            block_count_mean=("block_count", "mean"),
            avg_block_len_mean=("avg_block_len", "mean"),
            short_line_ratio_mean=("short_line_ratio", "mean"),
            table_detected_rate=("table_detected_int", "mean"),
            table_line_count_mean=("table_line_count", "mean"),
            table_text_ratio_mean=("table_text_ratio", "mean"),
            html_table_tag_count_mean=("html_table_tag_count", "mean"),
            html_td_count_mean=("html_td_count", "mean"),
            html_th_count_mean=("html_th_count", "mean"),
            avg_sentence_len_mean=("avg_sentence_len", "mean"),
            broken_sentence_ratio_recomputed_mean=("broken_sentence_ratio_recomputed", "mean"),
            long_block_ratio_mean=("long_block_ratio", "mean"),
            empty_block_ratio_mean=("empty_block_ratio", "mean"),
        )
        .sort_values("final_score_v2_mean", ascending=False)
    )
    summary["success_rate"] = summary["success_count"] / summary["sample_count"].clip(lower=1)
    return summary


def build_summary_by_doc_type(results_df: pd.DataFrame) -> pd.DataFrame:
    df = results_df.copy()
    numeric_columns = [
        "final_score_v2",
        "rouge_l",
        "coverage_score",
        "structure_score",
        "table_score",
        "rag_readiness_score",
    ]
    for column in numeric_columns:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    df["success_int"] = df["success"].astype(str).str.lower().eq("true").astype(int)
    return (
        df.groupby(["doc_type", "parser_name"], as_index=False)
        .agg(
            sample_count=("doc_id", "count"),
            success_rate=("success_int", "mean"),
            final_score_v2_mean=("final_score_v2", "mean"),
            rouge_l_mean=("rouge_l", "mean"),
            coverage_score_mean=("coverage_score", "mean"),
            structure_score_mean=("structure_score", "mean"),
            table_score_mean=("table_score", "mean"),
            rag_readiness_score_mean=("rag_readiness_score", "mean"),
        )
        .sort_values(["doc_type", "final_score_v2_mean"], ascending=[True, False])
    )


def format_metric(value: Any) -> str:
    numeric = safe_float(value)
    if numeric is None or pd.isna(numeric):
        return "NA"
    return f"{numeric:.4f}"


def build_report(results_df: pd.DataFrame, summary_df: pd.DataFrame, doc_type_summary_df: pd.DataFrame) -> str:
    lines: list[str] = []
    lines.append("# Parser Eval Report V2")
    lines.append("")
    lines.append("## Why V2")
    lines.append("- Ground Truth was revised from LlamaParse outputs, so text-similarity-heavy scoring in V1 structurally favored LlamaParse.")
    lines.append("- V2 lowers the weight of `ROUGE-L` and shifts emphasis to structure retention, table usability, and downstream RAG readiness.")
    lines.append("- `CoverageScore` is made symmetric so both truncation and length inflation are penalized.")
    lines.append("- HTML table tags are explicitly detected because some parsers preserve tables as HTML fragments rather than markdown or plain text grids.")
    lines.append("- `broken_sentence_ratio` is recomputed on body-like paragraphs only, excluding titles, table rows, list items, short standalone lines, and likely headers/footers.")
    lines.append("")
    lines.append("## Dataset Scope")
    lines.append(f"- Documents: {results_df['doc_id'].nunique()}")
    lines.append(f"- Parsers: {results_df['parser_name'].nunique()}")
    lines.append(f"- Rows: {len(results_df)}")
    lines.append("")
    lines.append("## Parser Ranking")
    lines.append("")
    lines.append("| parser | final_score_v2 | rouge_l | coverage_score | structure_score | table_score | rag_readiness | success_rate |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for _, row in summary_df.iterrows():
        lines.append(
            "| {parser_name} | {final_score_v2_mean:.4f} | {rouge_l_mean:.4f} | {coverage_score_mean:.4f} | {structure_score_mean:.4f} | {table_score_mean} | {rag_readiness_score_mean:.4f} | {success_rate:.4f} |".format(
                parser_name=row["parser_name"],
                final_score_v2_mean=row["final_score_v2_mean"] if pd.notna(row["final_score_v2_mean"]) else 0.0,
                rouge_l_mean=row["rouge_l_mean"] if pd.notna(row["rouge_l_mean"]) else 0.0,
                coverage_score_mean=row["coverage_score_mean"] if pd.notna(row["coverage_score_mean"]) else 0.0,
                structure_score_mean=row["structure_score_mean"] if pd.notna(row["structure_score_mean"]) else 0.0,
                table_score_mean=(f"{row['table_score_mean']:.4f}" if pd.notna(row["table_score_mean"]) else "NA"),
                rag_readiness_score_mean=row["rag_readiness_score_mean"] if pd.notna(row["rag_readiness_score_mean"]) else 0.0,
                success_rate=row["success_rate"] if pd.notna(row["success_rate"]) else 0.0,
            )
        )

    if not summary_df.empty:
        best_final = summary_df.iloc[0]["parser_name"]
        best_structure = summary_df.sort_values("structure_score_mean", ascending=False).iloc[0]["parser_name"]
        table_ranked = summary_df.dropna(subset=["table_score_mean"]).sort_values("table_score_mean", ascending=False)
        best_table = table_ranked.iloc[0]["parser_name"] if not table_ranked.empty else "NA"
        best_rag = summary_df.sort_values("rag_readiness_score_mean", ascending=False).iloc[0]["parser_name"]
        lines.append("")
        lines.append("## Short Observations")
        lines.append(f"- Overall V2 leader: `{best_final}`")
        lines.append(f"- Strongest structure preservation: `{best_structure}`")
        lines.append(f"- Strongest table usability on table-applicable docs: `{best_table}`")
        lines.append(f"- Strongest RAG readiness: `{best_rag}`")
        lines.append("- Compared with V1, V2 suppresses the dominance of GT-similarity and makes non-reference dimensions materially affect ranking.")

    anomalous = results_df[
        (pd.to_numeric(results_df["coverage_score"], errors="coerce") < 0.55)
        | (pd.to_numeric(results_df["structure_score"], errors="coerce") < 0.35)
        | (pd.to_numeric(results_df["rag_readiness_score"], errors="coerce") < 0.35)
        | (
            pd.to_numeric(results_df["table_score"], errors="coerce").notna()
            & (pd.to_numeric(results_df["table_score"], errors="coerce") < 0.20)
        )
    ].copy()
    anomalous = anomalous.sort_values(["final_score_v2", "doc_id"], ascending=[True, True]).head(20)
    lines.append("")
    lines.append("## Low-Score / Risk Samples")
    if anomalous.empty:
        lines.append("- None")
    else:
        lines.append("")
        lines.append("| doc_id | doc_type | parser | final_score_v2 | structure_score | table_score | rag_readiness | note |")
        lines.append("|---|---|---|---:|---:|---:|---:|---|")
        for _, row in anomalous.iterrows():
            note_bits: list[str] = []
            if safe_float(row["coverage_score"]) is not None and safe_float(row["coverage_score"]) < 0.55:
                note_bits.append("coverage mismatch")
            if safe_float(row["structure_score"]) is not None and safe_float(row["structure_score"]) < 0.35:
                note_bits.append("weak structure")
            if safe_float(row["table_score"]) is not None and safe_float(row["table_score"]) < 0.20:
                note_bits.append("weak table preservation")
            if safe_float(row["rag_readiness_score"]) is not None and safe_float(row["rag_readiness_score"]) < 0.35:
                note_bits.append("weak RAG readiness")
            lines.append(
                f"| {row['doc_id']} | {row['doc_type'] or 'NA'} | {row['parser_name']} | {format_metric(row['final_score_v2'])} | {format_metric(row['structure_score'])} | {format_metric(row['table_score'])} | {format_metric(row['rag_readiness_score'])} | {', '.join(note_bits)} |"
            )

    if not doc_type_summary_df.empty:
        lines.append("")
        lines.append("## By Document Type")
        for doc_type, group in doc_type_summary_df.groupby("doc_type"):
            group_sorted = group.sort_values("final_score_v2_mean", ascending=False)
            top_row = group_sorted.iloc[0]
            lines.append(
                f"- `{doc_type}`: top parser is `{top_row['parser_name']}` with final_score_v2={top_row['final_score_v2_mean']:.4f}, "
                f"structure={top_row['structure_score_mean']:.4f}, table={format_metric(top_row['table_score_mean'])}, rag={top_row['rag_readiness_score_mean']:.4f}"
            )

    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    results_path = (REPO_ROOT / args.results).resolve()
    manifest_path = (REPO_ROOT / args.manifest).resolve()
    subset_path = (REPO_ROOT / args.subset).resolve()
    output_dir = (REPO_ROOT / args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    logger = get_logger("parser_eval_v2", EXP_ROOT / "outputs" / "logs" / "parser_eval_v2.log")
    logger.info("Loading results=%s manifest=%s subset=%s", results_path, manifest_path, subset_path)

    results_df = load_csv(results_path)
    manifest_df = load_csv(manifest_path)
    subset_df = load_csv(subset_path)
    if results_df.empty:
        raise FileNotFoundError(f"Missing or empty parser results: {results_path}")
    if manifest_df.empty:
        raise FileNotFoundError(f"Missing or empty manifest: {manifest_path}")

    manifest_root = manifest_path.parent
    manifest_by_doc = {str(row["doc_id"]).strip(): row.to_dict() for _, row in manifest_df.iterrows()}
    subset_by_doc = {str(row["doc_id"]).strip(): row.to_dict() for _, row in subset_df.iterrows()}

    output_rows: list[dict[str, Any]] = []
    for _, base_row in results_df.iterrows():
        doc_id = str(base_row.get("doc_id", "")).strip()
        parser_name = str(base_row.get("parser_name", "")).strip()
        if not doc_id or not parser_name:
            continue

        parser_dir, manifest_status, manifest_error = resolve_parser_dir(doc_id, parser_name, manifest_by_doc, manifest_root)
        success = as_bool(base_row.get("success", "")) and parser_dir is not None and parser_dir.exists()
        error_message = str(base_row.get("error_message", "")).strip() or manifest_error
        doc_type = get_doc_type(doc_id, subset_by_doc, manifest_by_doc)
        table_expected = infer_table_expected(doc_id, doc_type, subset_by_doc)

        try:
            if parser_dir is None or not parser_dir.exists():
                raise FileNotFoundError(f"Parser output directory not found: {parser_dir}")

            content = load_parser_content_v2(
                parser_name=parser_name,
                parser_dir=parser_dir,
                success=success,
                error_message=error_message or manifest_error,
            )
            structure = enhanced_structure_metrics(content)
            table = enhanced_table_metrics(content, table_expected)
            rag = recomputed_rag_metrics(content)

            rouge_l = safe_float(base_row.get("rouge_l"))
            coverage_rate = safe_float(base_row.get("coverage_rate"))
            coverage_score = symmetric_coverage_score(coverage_rate)
            structure_score = safe_float(structure["structure_score"])
            table_score = safe_float(table["table_score"])
            rag_score = safe_float(rag["rag_readiness_score"])
            final_score = final_score_v2(
                rouge_l=rouge_l,
                coverage_score=coverage_score,
                structure_score=structure_score,
                table_score=table_score,
                rag_readiness_score=rag_score,
            )

            row = EvalResultV2(
                doc_id=doc_id,
                doc_type=doc_type,
                table_expected=("yes" if table_expected is True else "no" if table_expected is False else "unknown"),
                parser_name=parser_name,
                success=success,
                error_message=error_message or manifest_error,
                rouge_l=rouge_l,
                coverage_rate=coverage_rate,
                coverage_score=coverage_score,
                title_count=int(structure["title_count"]) if structure["title_count"] is not None else None,
                block_count=int(structure["block_count"]) if structure["block_count"] is not None else None,
                avg_block_len=safe_float(structure["avg_block_len"]),
                short_line_ratio=safe_float(structure["short_line_ratio"]),
                table_detected=bool(table["table_detected"]) if table["table_detected"] is not None else None,
                table_line_count=int(table["table_line_count"]) if table["table_line_count"] is not None else None,
                table_text_ratio=safe_float(table["table_text_ratio"]),
                html_table_tag_count=int(table["html_table_tag_count"]) if table["html_table_tag_count"] is not None else None,
                html_td_count=int(table["html_td_count"]) if table["html_td_count"] is not None else None,
                html_th_count=int(table["html_th_count"]) if table["html_th_count"] is not None else None,
                table_score=table_score,
                avg_sentence_len=safe_float(rag["avg_sentence_len"]),
                broken_sentence_ratio_recomputed=safe_float(rag["broken_sentence_ratio_recomputed"]),
                long_block_ratio=safe_float(rag["long_block_ratio"]),
                empty_block_ratio=safe_float(rag["empty_block_ratio"]),
                structure_score=structure_score,
                rag_readiness_score=rag_score,
                final_score_v2=final_score,
            )
            output_rows.append(row.to_row())
        except Exception as exc:
            logger.exception("V2 evaluation failed for doc_id=%s parser=%s", doc_id, parser_name)
            output_rows.append(
                EvalResultV2(
                    doc_id=doc_id,
                    doc_type=doc_type,
                    table_expected=("yes" if table_expected is True else "no" if table_expected is False else "unknown"),
                    parser_name=parser_name,
                    success=False,
                    error_message=str(exc),
                    rouge_l=safe_float(base_row.get("rouge_l")),
                    coverage_rate=safe_float(base_row.get("coverage_rate")),
                    coverage_score=symmetric_coverage_score(safe_float(base_row.get("coverage_rate"))),
                    title_count=None,
                    block_count=None,
                    avg_block_len=None,
                    short_line_ratio=None,
                    table_detected=None,
                    table_line_count=None,
                    table_text_ratio=None,
                    html_table_tag_count=None,
                    html_td_count=None,
                    html_th_count=None,
                    table_score=None,
                    avg_sentence_len=None,
                    broken_sentence_ratio_recomputed=None,
                    long_block_ratio=None,
                    empty_block_ratio=None,
                    structure_score=None,
                    rag_readiness_score=None,
                    final_score_v2=None,
                ).to_row()
            )

    output_df = pd.DataFrame(output_rows)
    summary_df = build_summary(output_df)
    doc_type_summary_df = build_summary_by_doc_type(output_df)
    report = build_report(output_df, summary_df, doc_type_summary_df)

    results_v2_path = output_dir / "parser_results_v2.csv"
    summary_v2_path = output_dir / "parser_results_summary_v2.csv"
    doc_type_summary_v2_path = output_dir / "parser_results_summary_by_doc_type_v2.csv"
    report_v2_path = output_dir / "parser_eval_report_v2.md"

    output_df.to_csv(results_v2_path, index=False, encoding="utf-8-sig")
    summary_df.to_csv(summary_v2_path, index=False, encoding="utf-8-sig")
    doc_type_summary_df.to_csv(doc_type_summary_v2_path, index=False, encoding="utf-8-sig")
    report_v2_path.write_text(report, encoding="utf-8")

    logger.info(
        "V2 evaluation complete: rows=%s parsers=%s output_dir=%s",
        len(output_df),
        output_df["parser_name"].nunique() if not output_df.empty else 0,
        output_dir,
    )


if __name__ == "__main__":
    main()
