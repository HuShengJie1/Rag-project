"""Streamlit frontend for local RAG HTTP API."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional
from streamlit_pdf_viewer import pdf_viewer
import requests
import streamlit as st

DEFAULT_API_URL = "http://localhost:8000/api/rag"


def post_json(url: str, payload: Dict[str, Any], timeout: int = 60) -> Dict[str, Any]:
    resp = requests.post(url, json=payload, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def extract_page(metadata: Dict[str, Any]) -> Optional[int]:
    value = metadata.get("page")
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def extract_doc_name(metadata: Dict[str, Any], fallback: str = "unknown") -> str:
    for key in ("source", "source_file", "file_name", "document", "doc_name"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return fallback


def build_pdf_link(
    metadata: Dict[str, Any],
    doc_name: str,
    page: Optional[int],
    pdf_base_url: str,
    pdf_base_dir: str,
) -> Optional[str]:
    file_path = metadata.get("file_path")
    if isinstance(file_path, str) and file_path.strip():
        url = f"file:///{Path(file_path).resolve().as_posix()}"
    else:
        pdf_name = doc_name
        lowered = doc_name.lower()
        if lowered.endswith((".md", ".txt")):
            pdf_name = f"{Path(doc_name).stem}.pdf"
        if pdf_base_url:
            url = f"{pdf_base_url.rstrip('/')}/{pdf_name}"
        elif pdf_base_dir:
            pdf_path = Path(pdf_base_dir) / pdf_name
            url = f"file:///{pdf_path.resolve().as_posix()}"
        else:
            return None
    if page:
        return f"{url}#page={page}"
    return url


def render_evidence_card(item: Dict[str, Any], pdf_base_url: str, pdf_base_dir: str) -> None:
    metadata = item.get("metadata") or {}
    if not isinstance(metadata, dict):
        metadata = {}
    doc_name = extract_doc_name(metadata)
    page = extract_page(metadata)
    preview = item.get("preview") or ""
    chunk_id = item.get("chunk_id") or ""
    link = build_pdf_link(metadata, doc_name, page, pdf_base_url, pdf_base_dir)

    with st.container(border=True):
        st.markdown(f"**{doc_name}**")
        st.markdown(f"页码：{page if page is not None else '页码未知'}")
        st.markdown(f"chunk_id：`{chunk_id}`")
        if preview:
            st.markdown(preview)
        if link:
            st.markdown(f"[查看原文]({link})")


def main() -> None:
    st.set_page_config(page_title="工程认证文档问答系统", layout="wide")
    st.title("工程认证文档问答系统")

    with st.sidebar:
        api_url = st.text_input("API URL", value=DEFAULT_API_URL)
        pdf_base_url = st.text_input("PDF Base URL (optional)", value="")
        pdf_base_dir = st.text_input("PDF Base Dir (optional)", value="")
        top_k = st.number_input("Top K", min_value=1, max_value=20, value=5, step=1)
        debug = st.checkbox("Request retrieved details", value=True)

    query = st.text_area("请输入问题", value="", height=120)
    submit = st.button("查询", type="primary")

    if submit:
        if not query.strip():
            st.warning("请输入问题。")
            st.stop()

        payload: Dict[str, Any] = {
            "query": query.strip(),
            "top_k": int(top_k),
        }
        if debug:
            payload["debug"] = True

        with st.spinner("正在查询..."):
            try:
                response = post_json(api_url, payload)
            except requests.HTTPError as exc:
                st.error(f"HTTP error: {exc.response.status_code}")
                st.stop()
            except requests.RequestException as exc:
                st.error(f"Connection error: {exc}")
                st.stop()
            except json.JSONDecodeError:
                st.error("Invalid JSON response.")
                st.stop()

        answer = response.get("answer", "")
        retrieved = response.get("retrieved", [])
        
        print(type(retrieved))
        print(retrieved)
        st.markdown("### Answer")
        st.markdown(f"> {answer if answer else '(empty)'}")

        st.markdown("### Evidence")
        if isinstance(retrieved, list) and retrieved:
            for item in retrieved:
                if isinstance(item, dict):
                    with st.expander("证据详情", expanded=False):
                        render_evidence_card(item, pdf_base_url, pdf_base_dir)
        else:
            st.info("No retrieved details in response.")
    
        
if __name__ == "__main__":
    main()
