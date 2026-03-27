from __future__ import annotations

import argparse
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot parser evaluation figures for parsing-layer experiments.")
    parser.add_argument("--results", type=str, default="experiments/outputs/parsing_eval/parser_results.csv")
    parser.add_argument("--summary", type=str, default="experiments/outputs/parsing_eval/parser_results_summary.csv")
    parser.add_argument("--subset", type=str, default="experiments/parsing_eval/phase1_subset.csv")
    parser.add_argument("--output-dir", type=str, default="experiments/outputs/parsing_eval/figures")
    return parser.parse_args()


def configure_matplotlib() -> None:
    plt.rcParams["font.sans-serif"] = [
        "Microsoft YaHei",
        "SimHei",
        "Arial Unicode MS",
        "DejaVu Sans",
    ]
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.dpi"] = 150
    plt.rcParams["savefig.dpi"] = 300
    plt.rcParams["axes.titleweight"] = "bold"
    plt.rcParams["axes.edgecolor"] = "#444444"
    plt.rcParams["axes.linewidth"] = 0.8
    plt.rcParams["grid.color"] = "#D9D9D9"
    plt.rcParams["grid.linestyle"] = "--"
    plt.rcParams["grid.linewidth"] = 0.6


def load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def ensure_numeric(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    working = df.copy()
    for column in columns:
        if column in working.columns:
            working[column] = pd.to_numeric(working[column], errors="coerce")
    return working


def save_bar_chart(
    df: pd.DataFrame,
    value_col: str,
    output_path: Path,
    title: str,
    ylabel: str,
    color: str,
    invert: bool = False,
) -> None:
    working = df[["parser_name", value_col]].dropna().copy()
    if working.empty:
        return
    if invert:
        working[value_col] = 1 - working[value_col]

    fig, ax = plt.subplots(figsize=(8.4, 5.2))
    bars = ax.bar(working["parser_name"], working[value_col], color=color, edgecolor="#333333", linewidth=0.8)
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.grid(axis="y", alpha=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(axis="x", rotation=20)
    max_value = working[value_col].max()
    if pd.notna(max_value):
        ax.set_ylim(0, max(1.05 * max_value, 0.1))

    for bar in bars:
        height = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            height + max(max_value * 0.015, 0.005),
            f"{height:.3f}",
            ha="center",
            va="bottom",
            fontsize=8,
        )

    fig.tight_layout()
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)


def minmax_normalize(series: pd.Series, inverse: bool = False, log_scale: bool = False) -> pd.Series:
    values = series.astype(float).copy()
    if log_scale:
        values = values.apply(lambda x: math.log1p(max(x, 0.0)))
    min_v = values.min()
    max_v = values.max()
    if pd.isna(min_v) or pd.isna(max_v):
        normalized = pd.Series([0.0] * len(values), index=values.index)
    elif abs(max_v - min_v) < 1e-12:
        normalized = pd.Series([1.0] * len(values), index=values.index)
    else:
        normalized = (values - min_v) / (max_v - min_v)
    return 1 - normalized if inverse else normalized


def coverage_closeness(series: pd.Series) -> pd.Series:
    values = series.astype(float).copy()
    return values.apply(lambda x: max(0.0, 1.0 - min(abs(x - 1.0), 1.0)))


def build_radar_scores(summary_df: pd.DataFrame) -> pd.DataFrame:
    working = summary_df.copy()
    working["text_quality"] = (
        minmax_normalize(working["rouge_l_mean"])
        + coverage_closeness(working["coverage_rate_mean"])
    ) / 2.0
    working["structure_quality"] = (
        minmax_normalize(working["title_count_mean"], log_scale=True)
        + minmax_normalize(working["block_count_mean"], log_scale=True)
        + minmax_normalize(working["short_line_ratio_mean"], inverse=True)
    ) / 3.0
    working["table_quality"] = (
        minmax_normalize(working["table_detected_rate"])
        + minmax_normalize(working["table_line_count_mean"], log_scale=True)
        + minmax_normalize(working["table_text_ratio_mean"])
    ) / 3.0
    working["rag_readiness"] = (
        minmax_normalize(working["broken_sentence_ratio_mean"], inverse=True)
        + minmax_normalize(working["long_block_ratio_mean"], inverse=True)
        + minmax_normalize(working["empty_block_ratio_mean"], inverse=True)
    ) / 3.0
    return working


def save_radar_chart(summary_df: pd.DataFrame, output_path: Path) -> None:
    working = build_radar_scores(summary_df)
    metrics = ["text_quality", "structure_quality", "table_quality", "rag_readiness"]
    labels = ["Text Quality", "Structure", "Table", "RAG Ready"]
    angles = [n / float(len(metrics)) * 2 * math.pi for n in range(len(metrics))]
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(7.2, 7.2), subplot_kw={"polar": True})
    color_cycle = ["#1f77b4", "#d62728", "#2ca02c", "#ff7f0e", "#9467bd", "#8c564b", "#17becf"]

    for idx, row in working.iterrows():
        values = [float(row[m]) for m in metrics]
        values += values[:1]
        color = color_cycle[idx % len(color_cycle)]
        ax.plot(angles, values, linewidth=2.0, label=row["parser_name"], color=color)
        ax.fill(angles, values, color=color, alpha=0.08)

    ax.set_theta_offset(math.pi / 2)
    ax.set_theta_direction(-1)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels)
    ax.set_ylim(0, 1)
    ax.set_yticks([0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_yticklabels(["0.2", "0.4", "0.6", "0.8", "1.0"], fontsize=8)
    ax.set_title("Parser Comparison Across Four Normalized Dimensions", pad=22)
    ax.grid(alpha=0.7)
    ax.legend(loc="upper right", bbox_to_anchor=(1.25, 1.12), frameon=False)

    fig.tight_layout()
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)


def save_doc_type_bar(results_df: pd.DataFrame, subset_df: pd.DataFrame, output_path: Path) -> bool:
    if results_df.empty or subset_df.empty or "doc_type_inferred" not in subset_df.columns:
        return False

    meta = subset_df[["doc_id", "doc_type_inferred"]].copy()
    meta["doc_id"] = meta["doc_id"].astype(str)
    working = results_df.copy()
    working["doc_id"] = working["doc_id"].astype(str)
    working["rouge_l"] = pd.to_numeric(working["rouge_l"], errors="coerce")
    merged = working.merge(meta, on="doc_id", how="left")
    merged = merged.dropna(subset=["rouge_l"])
    if merged.empty:
        return False

    pivot = (
        merged.groupby(["doc_type_inferred", "parser_name"], as_index=False)["rouge_l"]
        .mean()
        .pivot(index="doc_type_inferred", columns="parser_name", values="rouge_l")
        .fillna(0.0)
    )
    if pivot.empty:
        return False

    fig, ax = plt.subplots(figsize=(11, 5.6))
    x = range(len(pivot.index))
    parser_names = list(pivot.columns)
    width = 0.12 if len(parser_names) >= 5 else 0.18
    offsets = [((i - (len(parser_names) - 1) / 2) * width) for i in range(len(parser_names))]
    color_cycle = ["#1f77b4", "#d62728", "#2ca02c", "#ff7f0e", "#9467bd", "#8c564b", "#17becf"]

    for idx, parser_name in enumerate(parser_names):
        values = pivot[parser_name].tolist()
        ax.bar(
            [pos + offsets[idx] for pos in x],
            values,
            width=width,
            label=parser_name,
            color=color_cycle[idx % len(color_cycle)],
            edgecolor="#333333",
            linewidth=0.5,
        )

    ax.set_title("Average ROUGE-L by Document Type and Parser")
    ax.set_ylabel("ROUGE-L")
    ax.set_xticks(list(x))
    ax.set_xticklabels(pivot.index.tolist(), rotation=20)
    ax.grid(axis="y", alpha=0.8)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, ncol=3)

    fig.tight_layout()
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)
    return True


def write_notes(path: Path, doc_type_figure_generated: bool) -> None:
    lines = [
        "# Figure Notes",
        "",
        "- `bar_rouge_l.png`: compares average ROUGE-L across parsers. Higher is better.",
        "- `bar_coverage_rate.png`: compares average coverage_rate across parsers. Values closer to 1 indicate parser output length is closer to GT length.",
        "- `bar_structure_quality.png`: shows a structure-oriented metric using inverse `short_line_ratio_mean`. Higher suggests fewer fragmented short lines.",
        "- `bar_table_quality.png`: compares `table_detected_rate`, reflecting how often table traces are preserved.",
        "- `bar_rag_readiness.png`: shows `1 - broken_sentence_ratio_mean`. Higher suggests cleaner sentence continuity for downstream RAG chunking.",
        "- `radar_parser_overview.png`: aggregates four normalized dimensions: text quality, structure quality, table quality, and RAG readiness. Larger area generally indicates stronger overall parsing performance.",
    ]
    if doc_type_figure_generated:
        lines.append("- `bar_doc_type_rouge_l.png`: grouped bar chart comparing ROUGE-L by document type and parser.")
    else:
        lines.append("- `bar_doc_type_rouge_l.png` was skipped because no usable doc-type mapping was available.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    configure_matplotlib()

    results_path = (REPO_ROOT / args.results).resolve()
    summary_path = (REPO_ROOT / args.summary).resolve()
    subset_path = (REPO_ROOT / args.subset).resolve()
    output_dir = (REPO_ROOT / args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    results_df = load_csv(results_path)
    summary_df = load_csv(summary_path)
    subset_df = load_csv(subset_path)

    summary_df = ensure_numeric(
        summary_df,
        [
            "rouge_l_mean",
            "coverage_rate_mean",
            "short_line_ratio_mean",
            "table_detected_rate",
            "table_text_ratio_mean",
            "table_line_count_mean",
            "broken_sentence_ratio_mean",
            "long_block_ratio_mean",
            "empty_block_ratio_mean",
            "title_count_mean",
            "block_count_mean",
        ],
    )

    save_bar_chart(
        summary_df,
        value_col="rouge_l_mean",
        output_path=output_dir / "bar_rouge_l.png",
        title="Average ROUGE-L by Parser",
        ylabel="ROUGE-L",
        color="#4C78A8",
    )
    save_bar_chart(
        summary_df,
        value_col="coverage_rate_mean",
        output_path=output_dir / "bar_coverage_rate.png",
        title="Average Coverage Rate by Parser",
        ylabel="Coverage Rate",
        color="#F58518",
    )
    save_bar_chart(
        summary_df,
        value_col="short_line_ratio_mean",
        output_path=output_dir / "bar_structure_quality.png",
        title="Structure Quality by Parser",
        ylabel="1 - Short Line Ratio",
        color="#54A24B",
        invert=True,
    )
    save_bar_chart(
        summary_df,
        value_col="table_detected_rate",
        output_path=output_dir / "bar_table_quality.png",
        title="Table Preservation by Parser",
        ylabel="Table Detected Rate",
        color="#B279A2",
    )
    save_bar_chart(
        summary_df,
        value_col="broken_sentence_ratio_mean",
        output_path=output_dir / "bar_rag_readiness.png",
        title="RAG Readiness by Parser",
        ylabel="1 - Broken Sentence Ratio",
        color="#E45756",
        invert=True,
    )
    save_radar_chart(summary_df, output_dir / "radar_parser_overview.png")
    doc_type_generated = save_doc_type_bar(results_df, subset_df, output_dir / "bar_doc_type_rouge_l.png")
    write_notes(output_dir / "figure_notes.md", doc_type_generated)


if __name__ == "__main__":
    main()
