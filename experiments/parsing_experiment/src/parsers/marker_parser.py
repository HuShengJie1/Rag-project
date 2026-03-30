from __future__ import annotations

import json
import os
import tempfile
import time
import warnings
from pathlib import Path
from typing import Any

from .base import BaseParser, ParseResult


class MarkerParser(BaseParser):
    name = "marker"

    def _expand_env(self, value: Any) -> Any:
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.startswith("${") and stripped.endswith("}"):
                env_name = stripped[2:-1].strip()
                return os.getenv(env_name, "")
            return value
        if isinstance(value, dict):
            return {k: self._expand_env(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._expand_env(v) for v in value]
        return value

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
                    return self._expand_env(nested)
                return self._expand_env(parser_cfg)
        nested_cfg = cfg.get(self.name)
        if isinstance(nested_cfg, dict):
            nested = nested_cfg.get("config")
            if isinstance(nested, dict):
                return self._expand_env(nested)
            return self._expand_env(nested_cfg)
        return self._expand_env(cfg)

    def _service_prefix(self, config: dict[str, Any]) -> str | None:
        llm_service = str(config.get("llm_service", "")).strip()
        if not llm_service:
            return None
        return llm_service.split(".")[-1]

    def _build_cli_args(self, file_path: Path, output_dir: Path, config: dict[str, Any]) -> list[str]:
        args = [
            str(file_path),
            "--output_dir",
            str(output_dir),
            "--output_format",
            "markdown",
        ]
        if config.get("disable_multiprocessing", True):
            args.append("--disable_multiprocessing")
        if config.get("disable_tqdm", True):
            args.append("--disable_tqdm")
        if config.get("disable_image_extraction", False):
            args.append("--disable_image_extraction")

        page_range = config.get("page_range")
        if page_range:
            args.extend(["--page_range", str(page_range)])

        config_json = config.get("config_json")
        if config_json:
            args.extend(["--config_json", str(config_json)])

        if config.get("use_llm", False):
            args.append("--use_llm")

        llm_service = config.get("llm_service")
        if llm_service:
            args.extend(["--llm_service", str(llm_service)])

        converter_cls = config.get("converter_cls")
        if converter_cls:
            args.extend(["--converter_cls", str(converter_cls)])

        processors = config.get("processors")
        if processors:
            if isinstance(processors, (list, tuple)):
                processors = ",".join(str(x) for x in processors if str(x).strip())
            args.extend(["--processors", str(processors)])

        service_prefix = self._service_prefix(config)
        service_config = config.get("service_config", {})
        if service_prefix and isinstance(service_config, dict):
            for key, value in service_config.items():
                if value in (None, "", []):
                    continue
                option = f"--{service_prefix}_{key}"
                if isinstance(value, bool):
                    if value:
                        args.append(option)
                    continue
                args.extend([option, str(value)])

        extra_cli_args = config.get("extra_cli_args", [])
        if isinstance(extra_cli_args, (list, tuple)):
            args.extend([str(arg) for arg in extra_cli_args if str(arg).strip()])

        return args

    def parse(self, file_path: str | Path, config: dict | None = None) -> ParseResult:
        start = time.perf_counter()
        result = ParseResult(parser_name=self.name)
        cfg = self._resolve_config(config)
        try:
            from marker.scripts.convert_single import convert_single_cli  # type: ignore
        except Exception as e:
            result.success = False
            result.error_message = f"Marker not installed or API incompatible ({e})"
            result.elapsed_time = time.perf_counter() - start
            return result

        try:
            path = Path(file_path)
            with tempfile.TemporaryDirectory(prefix="marker_parse_") as tmpdir:
                output_root = Path(tmpdir)
                cli_args = self._build_cli_args(path, output_root, cfg)
                with warnings.catch_warnings():
                    warnings.filterwarnings(
                        "ignore",
                        message=r"The parameter .* is used more than once.*",
                        category=UserWarning,
                    )
                    convert_single_cli.main(args=cli_args, standalone_mode=False)

                marker_output_dir = output_root / path.stem
                md_path = marker_output_dir / f"{path.stem}.md"
                meta_path = marker_output_dir / f"{path.stem}_meta.json"

                if not md_path.exists():
                    raise FileNotFoundError(f"Marker output not found: {md_path}")
                md = md_path.read_text(encoding="utf-8", errors="ignore")

                if meta_path.exists():
                    try:
                        meta = json.loads(meta_path.read_text(encoding="utf-8"))
                        for page in meta.get("page_stats", []):
                            page_id = page.get("page_id")
                            page_no = int(page_id) + 1 if isinstance(page_id, int) else None
                            result.page_metadata.append(
                                {
                                    "page_no": page_no,
                                    "text_extraction_method": page.get("text_extraction_method"),
                                    "block_counts": page.get("block_counts", []),
                                }
                            )
                    except Exception:
                        # Keep parsing result usable even if marker metadata schema changes.
                        pass

            result.markdown = md
            result.raw_text = md or ""
            result.structured_blocks.append(
                {
                    "block_type": "markdown",
                    "text": md or "",
                    "page_no": None,
                }
            )
        except Exception as e:
            result.success = False
            result.error_message = str(e)
        finally:
            result.elapsed_time = time.perf_counter() - start
        return result
