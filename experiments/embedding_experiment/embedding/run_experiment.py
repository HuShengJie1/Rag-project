from __future__ import annotations

import argparse
import gc
import re
from collections import defaultdict
from pathlib import Path

import pandas as pd

from embedding_loader import ALLOWED_MODELS, embed_chunks, embed_queries, load_embedding_model
from evaluation import evaluate_retrieval
from markdown_splitter import DEFAULT_HEADERS_TO_SPLIT_ON, build_chunk_corpus
from retrieval import search_top_k


EXPERIMENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = EXPERIMENT_DIR.parents[2]
DEFAULT_QA_PATH = EXPERIMENT_DIR / "工程教育认证RAG评测黄金测试集报告（50对QA）.xlsx"
DEFAULT_MD_DIR = PROJECT_ROOT / "data/parsed/md"
DEFAULT_OUTPUT_DIR = EXPERIMENT_DIR / "outputs"


def normalize_doc_name(name: str) -> str:
    text = str(name).strip()
    text = text.replace("\u3000", " ").replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.lower()


def parse_qa_id_list(value: object) -> list[int]:
    if value is None:
        return []
    nums = re.findall(r"\d+", str(value))
    return [int(n) for n in nums]


def _detect_qa_sheets(excel_file: pd.ExcelFile, doc_map_sheet: str, explicit_sheets: list[str] | None) -> list[str]:
    if explicit_sheets:
        return explicit_sheets
    candidate = []
    for sheet in excel_file.sheet_names:
        if sheet == doc_map_sheet:
            continue
        df = pd.read_excel(excel_file, sheet_name=sheet, nrows=1)
        if "问题" in df.columns:
            candidate.append(sheet)
    return candidate


def _extract_attachment_key(text: str) -> str | None:
    match = re.search(r"附件\s*\d+-\d+", str(text))
    if not match:
        return None
    return re.sub(r"\s+", "", match.group(0)).lower()


def _build_doc_aliases(md_dir: Path) -> tuple[dict[str, str], list[str]]:
    aliases: dict[str, str] = {}
    doc_names: list[str] = []
    for path in sorted(md_dir.glob("*.md")):
        doc_names.append(path.name)
        alias_keys = {
            normalize_doc_name(path.name),
            normalize_doc_name(path.stem),
        }
        for key in alias_keys:
            aliases.setdefault(key, path.name)
    return aliases, doc_names


def _resolve_doc_name(raw_name: str, aliases: dict[str, str], doc_names: list[str]) -> str | None:
    candidates = {
        normalize_doc_name(raw_name),
        normalize_doc_name(Path(raw_name).name),
        normalize_doc_name(Path(raw_name).stem),
    }
    for cand in candidates:
        if cand in aliases:
            return aliases[cand]

    raw_attachment = _extract_attachment_key(raw_name)
    if raw_attachment:
        matched = []
        for doc_name in doc_names:
            attachment = _extract_attachment_key(doc_name)
            if attachment and attachment == raw_attachment:
                matched.append(doc_name)
        if len(matched) == 1:
            return matched[0]

    raw_norm = normalize_doc_name(raw_name)
    fuzzy_candidates = [doc_name for doc_name in doc_names if raw_norm in normalize_doc_name(doc_name)]
    if len(fuzzy_candidates) == 1:
        return fuzzy_candidates[0]

    return None


def load_queries_and_ground_truth(
    qa_path: Path,
    *,
    md_dir: Path,
    doc_map_sheet: str,
    qa_sheets: list[str] | None = None,
) -> pd.DataFrame:
    excel_file = pd.ExcelFile(qa_path)
    selected_qa_sheets = _detect_qa_sheets(excel_file, doc_map_sheet, qa_sheets)
    if not selected_qa_sheets:
        raise ValueError("No QA sheets detected. Please pass --qa-sheets explicitly.")

    query_rows = []
    qa_id = 1
    for sheet in selected_qa_sheets:
        df = pd.read_excel(excel_file, sheet_name=sheet).fillna("")
        if "问题" not in df.columns:
            continue
        for _, row in df.iterrows():
            question = str(row.get("问题", "")).strip()
            if not question:
                continue
            query_rows.append(
                {
                    "qa_id": qa_id,
                    "source_sheet": sheet,
                    "dimension": str(row.get("维度", "")).strip(),
                    "question": question,
                    "standard_answer": str(row.get("标准答案", "")).strip(),
                    "core_snippet": str(row.get("原文核心片段", "")).strip(),
                }
            )
            qa_id += 1

    query_df = pd.DataFrame(query_rows)
    if query_df.empty:
        raise ValueError("No queries loaded from QA sheets.")

    mapping_df = pd.read_excel(excel_file, sheet_name=doc_map_sheet).fillna("")
    if "源文档名称" not in mapping_df.columns or "对应QA编号" not in mapping_df.columns:
        raise ValueError(f"Mapping sheet {doc_map_sheet!r} must contain '源文档名称' and '对应QA编号' columns.")

    aliases, doc_names = _build_doc_aliases(md_dir)
    attachment_to_docs: dict[str, list[str]] = defaultdict(list)
    for doc_name in doc_names:
        key = _extract_attachment_key(doc_name)
        if key:
            attachment_to_docs[key].append(doc_name)

    qa_to_doc_ids: dict[int, set[str]] = defaultdict(set)
    unresolved: dict[str, list[int]] = defaultdict(list)

    for _, row in mapping_df.iterrows():
        raw_doc_name = str(row.get("源文档名称", "")).strip()
        if not raw_doc_name:
            continue
        resolved_doc = _resolve_doc_name(raw_doc_name, aliases, doc_names)
        qa_ids = parse_qa_id_list(row.get("对应QA编号", ""))
        if resolved_doc is None:
            for qid in qa_ids:
                unresolved[raw_doc_name].append(qid)
            continue
        for qid in qa_ids:
            qa_to_doc_ids[qid].add(resolved_doc)

    if unresolved:
        unresolved_text = "; ".join(
            f"{name} -> {sorted(set(ids))}" for name, ids in sorted(unresolved.items(), key=lambda x: x[0])
        )
        raise ValueError(f"Failed to resolve these source document names from mapping sheet: {unresolved_text}")

    # Fallback: if mapping sheet misses a QA, infer from core snippet reference like "(附件1-11 第二十四条)".
    for row in query_df.itertuples(index=False):
        qid = int(row.qa_id)
        if qa_to_doc_ids.get(qid):
            continue
        key = _extract_attachment_key(getattr(row, "core_snippet", ""))
        if not key:
            continue
        matched_docs = attachment_to_docs.get(key, [])
        if len(matched_docs) == 1:
            qa_to_doc_ids[qid].add(matched_docs[0])

    query_df["ground_truth_doc_ids"] = query_df["qa_id"].map(lambda qid: "|".join(sorted(qa_to_doc_ids.get(int(qid), set()))))
    missing_gt = query_df[query_df["ground_truth_doc_ids"] == ""]
    if not missing_gt.empty:
        missing_ids = missing_gt["qa_id"].tolist()
        raise ValueError(f"Missing ground-truth document mapping for QA IDs: {missing_ids}")

    return query_df


def _safe_model_file_name(model_name: str) -> str:
    return model_name.replace("/", "__")


def _clear_torch_cache() -> None:
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description="EAC embedding model selection experiment.")
    parser.add_argument("--qa-path", type=Path, default=DEFAULT_QA_PATH)
    parser.add_argument("--qa-sheets", nargs="*", default=None, help="Optional QA sheets. Default: auto-detect sheets containing column '问题'.")
    parser.add_argument("--doc-map-sheet", type=str, default="Table 4")
    parser.add_argument("--md-dir", type=Path, default=DEFAULT_MD_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--chunk-size", type=int, default=700)
    parser.add_argument("--chunk-overlap", type=int, default=120)
    parser.add_argument("--min-chunk-chars", type=int, default=20)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--device", type=str, default=None)
    parser.add_argument("--disable-faiss", action="store_true")
    parser.add_argument("--chunk-preview-count", type=int, default=5)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)

    print("[Stage] Load queries and ground-truth mappings")
    query_df = load_queries_and_ground_truth(
        args.qa_path,
        md_dir=args.md_dir,
        doc_map_sheet=args.doc_map_sheet,
        qa_sheets=args.qa_sheets,
    )
    query_df.to_csv(args.output_dir / "queries_with_ground_truth.csv", index=False, encoding="utf-8-sig")
    print(f"Loaded {len(query_df)} queries.")

    selected_doc_ids = set()
    for text in query_df["ground_truth_doc_ids"]:
        selected_doc_ids.update([x for x in str(text).split("|") if x.strip()])
    print(f"[Stage] Build chunk corpus from {len(selected_doc_ids)} markdown documents")

    chunks = build_chunk_corpus(
        args.md_dir,
        selected_doc_ids=selected_doc_ids,
        headers_to_split_on=DEFAULT_HEADERS_TO_SPLIT_ON,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        min_chunk_chars=args.min_chunk_chars,
    )
    if not chunks:
        raise ValueError("No chunks generated. Please check markdown inputs and splitter parameters.")

    chunk_df = pd.DataFrame(chunks)
    chunk_df_to_save = chunk_df.copy()
    chunk_df_to_save["header_hierarchy"] = chunk_df_to_save["header_hierarchy"].apply(
        lambda x: " > ".join(x) if isinstance(x, list) else str(x)
    )
    chunk_df_to_save.to_csv(args.output_dir / "chunk_corpus.csv", index=False, encoding="utf-8-sig")

    chunk_preview_path = args.output_dir / "chunk_preview.csv"
    chunk_df_to_save.head(args.chunk_preview_count).to_csv(chunk_preview_path, index=False, encoding="utf-8-sig")
    print(f"Generated {len(chunks)} chunks. Preview saved to: {chunk_preview_path}")

    print("[Stage] Run retrieval experiment for each candidate model")
    summary_rows = []
    queries = query_df["question"].tolist()

    for model_name in ALLOWED_MODELS:
        print(f"  - Evaluating: {model_name}")
        row = {"model_name": model_name, "status": "failed", "backend": "", "error": ""}
        model = None
        try:
            model = load_embedding_model(model_name, device=args.device)
            doc_embeddings = embed_chunks(model, chunks, batch_size=args.batch_size, show_progress_bar=True)
            query_embeddings = embed_queries(
                model,
                model_name,
                queries,
                batch_size=args.batch_size,
                show_progress_bar=False,
            )

            retrieved_indices, retrieved_scores, backend = search_top_k(
                doc_embeddings,
                query_embeddings,
                top_k=args.top_k,
                use_faiss=not args.disable_faiss,
            )
            metrics, detail_df = evaluate_retrieval(
                query_df,
                retrieved_indices,
                retrieved_scores,
                chunks,
                k_values=(1, 5, 10),
            )

            detail_path = args.output_dir / f"{_safe_model_file_name(model_name)}_retrieval_details.csv"
            detail_df.to_csv(detail_path, index=False, encoding="utf-8-sig")

            row.update(
                {
                    "status": "ok",
                    "backend": backend,
                    "error": "",
                    **metrics,
                }
            )
            print(
                f"    done: mrr={metrics['mrr']:.4f}, "
                f"hit@1={metrics['hit@1']:.4f}, hit@5={metrics['hit@5']:.4f}, hit@10={metrics['hit@10']:.4f}"
            )
        except Exception as exc:
            row["error"] = str(exc)
            print(f"    failed: {exc}")
        finally:
            summary_rows.append(row)
            del model
            gc.collect()
            _clear_torch_cache()

    summary_df = pd.DataFrame(summary_rows)
    comparison_path = args.output_dir / "model_comparison.csv"
    summary_df.to_csv(comparison_path, index=False, encoding="utf-8-sig")

    ok_df = summary_df[summary_df["status"] == "ok"].copy()
    if ok_df.empty:
        raise RuntimeError(f"No model completed successfully. See: {comparison_path}")

    best = ok_df.sort_values(by=["mrr", "hit@1", "hit@5", "hit@10"], ascending=False).iloc[0]
    best_path = args.output_dir / "best_model.txt"
    best_path.write_text(
        "\n".join(
            [
                f"best_model={best['model_name']}",
                f"mrr={best['mrr']:.6f}",
                f"hit@1={best['hit@1']:.6f}",
                f"hit@5={best['hit@5']:.6f}",
                f"hit@10={best['hit@10']:.6f}",
            ]
        ),
        encoding="utf-8",
    )

    print("[Stage] Finished")
    print(f"Comparison saved to: {comparison_path}")
    print(f"Best model: {best['model_name']}")
    print(f"Best metrics: mrr={best['mrr']:.4f}, hit@1={best['hit@1']:.4f}, hit@5={best['hit@5']:.4f}, hit@10={best['hit@10']:.4f}")


if __name__ == "__main__":
    main()
