from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_OUTPUT_DIR = REPO_ROOT / "experiments" / "outputs" / "parsing_eval"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize parser evaluation results and run quality checks.")
    parser.add_argument("--results", type=str, default="experiments/outputs/parsing_eval/parser_results.csv")
    parser.add_argument("--subset", type=str, default="experiments/parsing_eval/phase1_subset.csv")
    parser.add_argument("--manifest", type=str, default="experiments/parsing_eval/manifest.csv")
    parser.add_argument("--output-dir", type=str, default="experiments/outputs/parsing_eval")
    return parser.parse_args()


def load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path).fillna("")


def normalize_doc_type(series: pd.Series) -> pd.Series:
    if "doc_type_inferred" in series.index and str(series["doc_type_inferred"]).strip():
        return pd.Series({"doc_type": str(series["doc_type_inferred"]).strip()})
    if "doc_type" in series.index and str(series["doc_type"]).strip():
        return pd.Series({"doc_type": str(series["doc_type"]).strip()})
    if "doc_type_raw" in series.index and str(series["doc_type_raw"]).strip():
        return pd.Series({"doc_type": str(series["doc_type_raw"]).strip()})
    return pd.Series({"doc_type": "unknown"})


def build_parser_summary(df: pd.DataFrame) -> pd.DataFrame:
    working = df.copy()
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
    for col in numeric_columns:
        if col in working.columns:
            working[col] = pd.to_numeric(working[col], errors="coerce")
    working["success_bool"] = working["success"].astype(str).str.lower().eq("true")
    working["table_detected_bool"] = working["table_detected"].astype(str).str.lower().eq("true")

    summary = (
        working.groupby("parser_name", as_index=False)
        .agg(
            sample_count=("doc_id", "count"),
            success_count=("success_bool", "sum"),
            rouge_l_mean=("rouge_l", "mean"),
            coverage_rate_mean=("coverage_rate", "mean"),
            text_length_mean=("text_length", "mean"),
            title_count_mean=("title_count", "mean"),
            block_count_mean=("block_count", "mean"),
            avg_block_len_mean=("avg_block_len", "mean"),
            short_line_ratio_mean=("short_line_ratio", "mean"),
            table_detected_rate=("table_detected_bool", "mean"),
            table_line_count_mean=("table_line_count", "mean"),
            table_text_ratio_mean=("table_text_ratio", "mean"),
            avg_sentence_len_mean=("avg_sentence_len", "mean"),
            broken_sentence_ratio_mean=("broken_sentence_ratio", "mean"),
            long_block_ratio_mean=("long_block_ratio", "mean"),
            empty_block_ratio_mean=("empty_block_ratio", "mean"),
        )
    )
    summary["success_rate"] = summary["success_count"] / summary["sample_count"].clip(lower=1)
    return summary.sort_values(["rouge_l_mean", "success_rate"], ascending=[False, False])


def build_doc_type_summary(df: pd.DataFrame) -> pd.DataFrame:
    working = df.copy()
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
    for col in numeric_columns:
        if col in working.columns:
            working[col] = pd.to_numeric(working[col], errors="coerce")
    working["success_bool"] = working["success"].astype(str).str.lower().eq("true")
    working["table_detected_bool"] = working["table_detected"].astype(str).str.lower().eq("true")

    summary = (
        working.groupby(["doc_type", "parser_name"], as_index=False)
        .agg(
            sample_count=("doc_id", "count"),
            success_rate=("success_bool", "mean"),
            rouge_l_mean=("rouge_l", "mean"),
            coverage_rate_mean=("coverage_rate", "mean"),
            text_length_mean=("text_length", "mean"),
            block_count_mean=("block_count", "mean"),
            table_detected_rate=("table_detected_bool", "mean"),
            broken_sentence_ratio_mean=("broken_sentence_ratio", "mean"),
        )
    )
    return summary.sort_values(["doc_type", "parser_name"])


def detect_row_anomalies(df: pd.DataFrame) -> list[dict[str, Any]]:
    anomalies: list[dict[str, Any]] = []
    working = df.copy()
    working["coverage_rate"] = pd.to_numeric(working["coverage_rate"], errors="coerce")
    working["text_length"] = pd.to_numeric(working["text_length"], errors="coerce")
    working["broken_sentence_ratio"] = pd.to_numeric(working["broken_sentence_ratio"], errors="coerce")

    for _, row in working.iterrows():
        doc_id = str(row["doc_id"])
        parser_name = str(row["parser_name"])
        if pd.notna(row["coverage_rate"]) and row["coverage_rate"] < 0.3:
            anomalies.append({"scope": "row", "type": "low_coverage", "doc_id": doc_id, "parser_name": parser_name, "value": row["coverage_rate"]})
        if pd.notna(row["coverage_rate"]) and row["coverage_rate"] > 1.5:
            anomalies.append({"scope": "row", "type": "high_coverage", "doc_id": doc_id, "parser_name": parser_name, "value": row["coverage_rate"]})
        if pd.notna(row["text_length"]) and float(row["text_length"]) == 0:
            anomalies.append({"scope": "row", "type": "zero_text_length", "doc_id": doc_id, "parser_name": parser_name, "value": 0})
        if pd.notna(row["broken_sentence_ratio"]) and row["broken_sentence_ratio"] >= 0.9:
            anomalies.append({"scope": "row", "type": "high_broken_sentence_ratio", "doc_id": doc_id, "parser_name": parser_name, "value": row["broken_sentence_ratio"]})
    return anomalies


def detect_parser_anomalies(summary_df: pd.DataFrame) -> list[dict[str, Any]]:
    anomalies: list[dict[str, Any]] = []
    for _, row in summary_df.iterrows():
        parser_name = str(row["parser_name"])
        table_rate = float(row["table_detected_rate"]) if pd.notna(row["table_detected_rate"]) else 0.0
        if table_rate <= 0.05:
            anomalies.append({"scope": "parser", "type": "table_detected_too_low", "parser_name": parser_name, "value": table_rate})
        if table_rate >= 0.95:
            anomalies.append({"scope": "parser", "type": "table_detected_too_high", "parser_name": parser_name, "value": table_rate})

        broken_ratio = float(row["broken_sentence_ratio_mean"]) if pd.notna(row["broken_sentence_ratio_mean"]) else 0.0
        if broken_ratio >= 0.85:
            anomalies.append({"scope": "parser", "type": "broken_sentence_ratio_too_high", "parser_name": parser_name, "value": broken_ratio})
    return anomalies


def build_observations(summary_df: pd.DataFrame) -> list[str]:
    observations: list[str] = []
    if summary_df.empty:
        return ["No parser results found."]

    rouge_df = summary_df.dropna(subset=["rouge_l_mean"])
    if not rouge_df.empty:
        top_rouge = rouge_df.sort_values("rouge_l_mean", ascending=False).iloc[0]
        observations.append(
            f"{top_rouge['parser_name']} has the highest average ROUGE-L ({float(top_rouge['rouge_l_mean']):.4f})."
        )

    sentence_df = summary_df.dropna(subset=["broken_sentence_ratio_mean"])
    if not sentence_df.empty:
        best_sentence = sentence_df.sort_values("broken_sentence_ratio_mean", ascending=True).iloc[0]
        observations.append(
            f"{best_sentence['parser_name']} has the lowest average broken_sentence_ratio ({float(best_sentence['broken_sentence_ratio_mean']):.4f})."
        )

    table_df = summary_df.dropna(subset=["table_detected_rate"])
    if not table_df.empty:
        best_table = table_df.sort_values("table_detected_rate", ascending=False).iloc[0]
        observations.append(
            f"{best_table['parser_name']} most frequently preserves table signals (table_detected_rate={float(best_table['table_detected_rate']):.4f})."
        )

    return observations


def build_report(
    results_df: pd.DataFrame,
    parser_summary_df: pd.DataFrame,
    doc_type_summary_df: pd.DataFrame,
    anomalies: list[dict[str, Any]],
) -> str:
    lines: list[str] = []
    lines.append("# Parser Eval Report")
    lines.append("")
    lines.append(f"- Total samples: {results_df['doc_id'].nunique() if not results_df.empty else 0}")
    lines.append(f"- Total parser rows: {len(results_df)}")
    lines.append(f"- Parsers: {parser_summary_df['parser_name'].nunique() if not parser_summary_df.empty else 0}")
    lines.append("")
    lines.append("## Parser Success")
    if parser_summary_df.empty:
        lines.append("- No summary available.")
    else:
        for _, row in parser_summary_df.iterrows():
            lines.append(
                f"- {row['parser_name']}: success_rate={float(row['success_rate']):.4f}, sample_count={int(row['sample_count'])}"
            )

    lines.append("")
    lines.append("## Metric Means")
    if parser_summary_df.empty:
        lines.append("- No metric summary available.")
    else:
        lines.append("| parser | rouge_l | coverage_rate | text_length | table_detected_rate | broken_sentence_ratio |")
        lines.append("|---|---:|---:|---:|---:|---:|")
        for _, row in parser_summary_df.iterrows():
            lines.append(
                "| {parser_name} | {rouge_l:.4f} | {coverage:.4f} | {text_length:.2f} | {table_rate:.4f} | {broken:.4f} |".format(
                    parser_name=row["parser_name"],
                    rouge_l=(float(row["rouge_l_mean"]) if pd.notna(row["rouge_l_mean"]) else 0.0),
                    coverage=(float(row["coverage_rate_mean"]) if pd.notna(row["coverage_rate_mean"]) else 0.0),
                    text_length=(float(row["text_length_mean"]) if pd.notna(row["text_length_mean"]) else 0.0),
                    table_rate=(float(row["table_detected_rate"]) if pd.notna(row["table_detected_rate"]) else 0.0),
                    broken=(float(row["broken_sentence_ratio_mean"]) if pd.notna(row["broken_sentence_ratio_mean"]) else 0.0),
                )
            )

    lines.append("")
    lines.append("## Anomalies")
    if anomalies:
        for anomaly in anomalies:
            if anomaly["scope"] == "row":
                lines.append(
                    f"- row | doc_id={anomaly['doc_id']} | parser={anomaly['parser_name']} | type={anomaly['type']} | value={float(anomaly['value']):.4f}"
                )
            else:
                lines.append(
                    f"- parser | parser={anomaly['parser_name']} | type={anomaly['type']} | value={float(anomaly['value']):.4f}"
                )
    else:
        lines.append("- None")

    lines.append("")
    lines.append("## Observations")
    for observation in build_observations(parser_summary_df):
        lines.append(f"- {observation}")

    lines.append("")
    lines.append("## By Doc Type")
    if doc_type_summary_df.empty:
        lines.append("- No doc type summary available.")
    else:
        for doc_type, group in doc_type_summary_df.groupby("doc_type"):
            lines.append(f"- {doc_type}: {len(group)} parser rows")

    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    results_path = (REPO_ROOT / args.results).resolve()
    subset_path = (REPO_ROOT / args.subset).resolve()
    manifest_path = (REPO_ROOT / args.manifest).resolve()
    output_dir = (REPO_ROOT / args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    results_df = load_csv(results_path)
    subset_df = load_csv(subset_path)
    manifest_df = load_csv(manifest_path)

    subset_meta = pd.DataFrame()
    if not subset_df.empty:
        subset_meta = subset_df[["doc_id"] + [col for col in ["doc_type_inferred", "doc_type_raw", "doc_dir"] if col in subset_df.columns]].copy()
    if subset_meta.empty and not manifest_df.empty:
        subset_meta = manifest_df[["doc_id"] + [col for col in ["doc_type", "doc_dir"] if col in manifest_df.columns]].copy()

    if not results_df.empty and not subset_meta.empty:
        results_df["doc_id"] = results_df["doc_id"].astype(str)
        subset_meta["doc_id"] = subset_meta["doc_id"].astype(str)
        results_df = results_df.merge(subset_meta, on="doc_id", how="left")
        results_df["doc_type"] = results_df.apply(normalize_doc_type, axis=1)["doc_type"]
    elif not results_df.empty:
        results_df["doc_type"] = "unknown"

    parser_summary_df = build_parser_summary(results_df) if not results_df.empty else pd.DataFrame()
    doc_type_summary_df = build_doc_type_summary(results_df) if not results_df.empty else pd.DataFrame()
    anomalies = detect_row_anomalies(results_df) + detect_parser_anomalies(parser_summary_df)

    parser_summary_df.to_csv(output_dir / "parser_results_summary.csv", index=False, encoding="utf-8-sig")
    doc_type_summary_df.to_csv(output_dir / "summary_by_doc_type.csv", index=False, encoding="utf-8-sig")
    (output_dir / "parser_eval_report.md").write_text(
        build_report(results_df, parser_summary_df, doc_type_summary_df, anomalies),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
