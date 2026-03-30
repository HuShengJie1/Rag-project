from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True)
class MinerURunResult:
    status: str
    error_message: str
    started_at: str
    finished_at: str
    duration_ms: int
    attempts: int
    return_code: int | None
    command: str


def build_mineru_command(
    *,
    mineru_bin: str,
    input_file: Path,
    output_dir: Path,
    backend: str,
) -> list[str]:
    command = [mineru_bin, "-p", str(input_file), "-o", str(output_dir)]
    if backend == "pipeline":
        command.extend(["-b", "pipeline"])
    return command


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _prepare_env(
    env_overrides: dict[str, str] | None,
) -> dict[str, str]:
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)

    # Force MinerU to read local model directories from ~/mineru.json.
    env["MINERU_MODEL_SOURCE"] = "local"

    # MinerU starts a local API on 127.0.0.1; ensure loopback never goes through proxies.
    no_proxy_items = {"127.0.0.1", "localhost"}
    existing = env.get("NO_PROXY", "") or env.get("no_proxy", "")
    if existing:
        no_proxy_items.update(item.strip() for item in existing.split(",") if item.strip())
    no_proxy_value = ",".join(sorted(no_proxy_items))
    env["NO_PROXY"] = no_proxy_value
    env["no_proxy"] = no_proxy_value

    return env


def _write_command_logs(
    output_dir: Path,
    *,
    attempt: int,
    stdout_text: str,
    stderr_text: str,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = output_dir / f"mineru_attempt_{attempt}.stdout.log"
    stderr_path = output_dir / f"mineru_attempt_{attempt}.stderr.log"
    stdout_path.write_text(stdout_text, encoding="utf-8")
    stderr_path.write_text(stderr_text, encoding="utf-8")


def _format_command(command: Sequence[str]) -> str:
    return " ".join(command)


def run_single_file(
    *,
    mineru_bin: str,
    input_file: Path,
    output_dir: Path,
    backend: str,
    retries: int = 0,
    dry_run: bool = False,
    timeout_sec: int | None = None,
    env_overrides: dict[str, str] | None = None,
) -> MinerURunResult:
    command = build_mineru_command(
        mineru_bin=mineru_bin,
        input_file=input_file,
        output_dir=output_dir,
        backend=backend,
    )
    command_str = _format_command(command)

    started_at = _iso_now()
    started_perf = time.perf_counter()

    if dry_run:
        finished_at = _iso_now()
        duration_ms = int((time.perf_counter() - started_perf) * 1000)
        return MinerURunResult(
            status="skipped",
            error_message="dry-run",
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=duration_ms,
            attempts=0,
            return_code=None,
            command=command_str,
        )

    final_error = ""
    final_code: int | None = None
    attempts = retries + 1
    env = _prepare_env(env_overrides)

    for attempt in range(1, attempts + 1):
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout_sec,
                env=env,
            )
            _write_command_logs(
                output_dir,
                attempt=attempt,
                stdout_text=completed.stdout,
                stderr_text=completed.stderr,
            )

            final_code = completed.returncode
            if completed.returncode == 0:
                finished_at = _iso_now()
                duration_ms = int((time.perf_counter() - started_perf) * 1000)
                return MinerURunResult(
                    status="success",
                    error_message="",
                    started_at=started_at,
                    finished_at=finished_at,
                    duration_ms=duration_ms,
                    attempts=attempt,
                    return_code=final_code,
                    command=command_str,
                )

            stderr = (completed.stderr or "").strip()
            final_error = stderr if stderr else f"mineru exited with code {completed.returncode}"

        except subprocess.TimeoutExpired as exc:
            stdout_text = exc.stdout if isinstance(exc.stdout, str) else ""
            stderr_text = exc.stderr if isinstance(exc.stderr, str) else ""
            _write_command_logs(
                output_dir,
                attempt=attempt,
                stdout_text=stdout_text,
                stderr_text=stderr_text,
            )
            final_error = f"timeout after {timeout_sec}s"
            final_code = None
        except FileNotFoundError:
            final_error = f"cannot find executable: {mineru_bin}"
            final_code = None
            break

    finished_at = _iso_now()
    duration_ms = int((time.perf_counter() - started_perf) * 1000)
    return MinerURunResult(
        status="failed",
        error_message=final_error,
        started_at=started_at,
        finished_at=finished_at,
        duration_ms=duration_ms,
        attempts=attempts,
        return_code=final_code,
        command=command_str,
    )
