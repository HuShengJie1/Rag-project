from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from .base import BaseParser, ParseResult


class LlamaParseParser(BaseParser):
    name = "llamaparse"

    def _resolve_config(self, config: dict | None) -> dict[str, Any]:
        if not isinstance(config, dict):
            return {}
        cfg: dict[str, Any] = config
        parsers = cfg.get("parsers")
        if isinstance(parsers, dict):
            parser_cfg = parsers.get(self.name, {})
            if isinstance(parser_cfg, dict):
                nested = parser_cfg.get("config")
                if isinstance(nested, dict):
                    return nested
                return parser_cfg
        nested_cfg = cfg.get(self.name)
        if isinstance(nested_cfg, dict):
            nested = nested_cfg.get("config")
            if isinstance(nested, dict):
                return nested
            return nested_cfg
        return cfg

    @staticmethod
    def _resolve_secret(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        if text.startswith("${") and text.endswith("}"):
            env_key = text[2:-1].strip()
            return os.getenv(env_key) or None
        return text

    @staticmethod
    def _coerce_expand(value: Any) -> list[str]:
        if isinstance(value, str):
            return [x.strip() for x in value.split(",") if x.strip()]
        if isinstance(value, (list, tuple)):
            return [str(x).strip() for x in value if str(x).strip()]
        return []

    @staticmethod
    def _extract_item_text(item: dict[str, Any]) -> str:
        for key in ("value", "text", "md", "csv", "html", "caption"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return value
        nested = item.get("items")
        if isinstance(nested, list):
            texts: list[str] = []
            for child in nested:
                if isinstance(child, dict):
                    child_text = LlamaParseParser._extract_item_text(child)
                    if child_text:
                        texts.append(child_text)
            return "\n".join(texts)
        return ""

    def parse(self, file_path: str | Path, config: dict | None = None) -> ParseResult:
        start = time.perf_counter()
        result = ParseResult(parser_name=self.name)
        cfg = self._resolve_config(config)
        api_key = (
            self._resolve_secret(cfg.get("api_key"))
            or os.getenv("LLAMAPARSE_EXPERIMENT_API_KEY")
            or os.getenv("LLAMAPARSE_API_KEY")
            or os.getenv("LLAMA_PARSE_API_KEY")
            or os.getenv("LLAMA_CLOUD_API_KEY")
        )
        if not api_key:
            result.success = False
            result.error_message = (
                "LlamaParse API key not configured. Set LLAMAPARSE_EXPERIMENT_API_KEY (or LLAMAPARSE_API_KEY / LLAMA_CLOUD_API_KEY)."
            )
            result.elapsed_time = time.perf_counter() - start
            return result

        try:
            from llama_cloud import LlamaCloud, file_from_path  # type: ignore
        except Exception as e:
            result.success = False
            result.error_message = f"Missing dependency: llama-cloud ({e})"
            result.elapsed_time = time.perf_counter() - start
            return result

        path = Path(file_path)
        tier = str(cfg.get("tier", "agentic_plus")).strip()
        expand = self._coerce_expand(cfg.get("expand")) or ["text", "markdown", "items", "metadata"]
        if tier.lower() == "fast":
            # FAST tier does not support markdown expansion.
            expand = [x for x in expand if not x.lower().startswith("markdown")]
            if not expand:
                expand = ["text", "items", "metadata"]
        parse_kwargs: dict[str, Any] = {
            "tier": tier,
            "version": str(cfg.get("version", "latest")),
            "upload_file": file_from_path(str(path)),
            "expand": expand,
            "polling_interval": float(cfg.get("polling_interval", 1.0)),
            "max_interval": float(cfg.get("max_interval", 5.0)),
            "timeout": float(cfg.get("timeout", 7200.0)),
            "backoff": str(cfg.get("backoff", "linear")),
            "verbose": bool(cfg.get("verbose", False)),
        }

        for optional_key in ("organization_id", "project_id", "client_name", "http_proxy"):
            value = cfg.get(optional_key)
            if value:
                parse_kwargs[optional_key] = value
        if "disable_cache" in cfg:
            parse_kwargs["disable_cache"] = bool(cfg.get("disable_cache"))
        for optional_object in (
            "agentic_options",
            "fast_options",
            "input_options",
            "output_options",
            "page_ranges",
            "processing_control",
            "processing_options",
        ):
            value = cfg.get(optional_object)
            if value:
                parse_kwargs[optional_object] = value

        client_kwargs: dict[str, Any] = {
            "api_key": api_key,
            "timeout": float(cfg.get("request_timeout", 120)),
            "max_retries": int(cfg.get("request_max_retries", 3)),
        }
        base_url = cfg.get("base_url")
        if base_url:
            client_kwargs["base_url"] = str(base_url)
        client = LlamaCloud(**client_kwargs)
        try:
            response = client.parsing.parse(**parse_kwargs)
            result.raw_text = (response.text_full or "").strip()
            if not result.raw_text and response.text:
                result.raw_text = "\n\n".join(
                    p.text for p in response.text.pages if getattr(p, "text", None)
                ).strip()

            markdown_full = (response.markdown_full or "").strip()
            if markdown_full:
                result.markdown = markdown_full
            elif response.markdown:
                per_page_markdown = [
                    p.markdown
                    for p in response.markdown.pages
                    if hasattr(p, "markdown") and getattr(p, "markdown", None)
                ]
                result.markdown = "\n\n".join(per_page_markdown).strip() or None

            if response.items:
                for page in response.items.pages:
                    page_no = int(getattr(page, "page_number", 0) or 0)
                    if not getattr(page, "success", False):
                        result.page_metadata.append(
                            {
                                "page_no": page_no,
                                "success": False,
                                "error": getattr(page, "error", "unknown page parse error"),
                            }
                        )
                        continue

                    result.page_metadata.append(
                        {
                            "page_no": page_no,
                            "success": True,
                            "page_width": getattr(page, "page_width", None),
                            "page_height": getattr(page, "page_height", None),
                        }
                    )
                    for item in getattr(page, "items", []):
                        item_dict = item.model_dump()
                        result.structured_blocks.append(
                            {
                                "block_type": item_dict.get("type", "unknown"),
                                "text": self._extract_item_text(item_dict),
                                "page_no": page_no,
                                "metadata": item_dict,
                            }
                        )

            if response.metadata and response.metadata.pages:
                result.page_metadata = [
                    {
                        "page_no": p.page_number,
                        **p.model_dump(),
                    }
                    for p in response.metadata.pages
                ]

            if not result.raw_text and result.markdown:
                result.raw_text = result.markdown

            if not (result.raw_text or result.markdown or result.structured_blocks):
                result.success = False
                result.error_message = "LlamaParse returned empty content"
        except Exception as e:
            result.success = False
            err = f"{e.__class__.__name__}: {e}"
            cause = getattr(e, "__cause__", None)
            if cause:
                err = f"{err} | cause={cause.__class__.__name__}: {cause}"
            result.error_message = err
        finally:
            client.close()
            result.elapsed_time = time.perf_counter() - start
        return result
