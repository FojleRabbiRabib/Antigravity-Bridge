"""Antigravity Bridge CLI interaction — subprocess calls to agy."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from . import config
from . import files


def _build_base_cmd() -> list[str]:
    cmd = ["agy"]
    if config.should_skip_permissions():
        cmd.append("--dangerously-skip-permissions")
    if config.should_sandbox():
        cmd.append("--sandbox")
    return cmd


def _run_agy(cmd: list[str], directory: str, timeout: int) -> tuple[bool, str, str]:
    try:
        result = subprocess.run(
            cmd,
            cwd=directory,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode == 0:
            output = result.stdout.strip() if result.stdout.strip() else "No output from Antigravity CLI"
            return True, output, ""
        else:
            error_msg = result.stderr.strip()
            if not error_msg:
                error_msg = f"Exit code {result.returncode}"
            if "authentication" in error_msg.lower() or "auth" in error_msg.lower():
                return False, f"Antigravity CLI Error: Authentication required. Details: {error_msg}", ""
            return False, f"Antigravity CLI Error: {error_msg}", ""
    except subprocess.TimeoutExpired:
        return False, f"Error: Antigravity CLI command timed out after {timeout} seconds. Try increasing timeout or simplifying your query.", ""
    except FileNotFoundError:
        return False, "Error: Antigravity CLI not found. Install with: curl -fsSL https://antigravity.google/cli/install.sh | bash", ""


def execute_antigravity_simple(
    query: str,
    directory: str = ".",
    timeout_seconds: int | None = None,
) -> str:
    if not shutil.which("agy"):
        return "Error: Antigravity CLI not found. Install with: curl -fsSL https://antigravity.google/cli/install.sh | bash"

    if not Path(directory).is_dir():
        return f"Error: Directory does not exist: {directory}"

    timeout = config.coerce_timeout(timeout_seconds)
    cmd = _build_base_cmd()

    if directory != ".":
        cmd.extend(["--add-dir", directory])

    cmd.extend(["--print", query])

    success, output, _ = _run_agy(cmd, directory, timeout)
    return output


def execute_antigravity_with_files(
    query: str,
    directory: str = ".",
    files_list: list[str] | None = None,
    timeout_seconds: int | None = None,
    mode: str = "inline",
) -> str:
    if not shutil.which("agy"):
        return "Error: Antigravity CLI not found. Install with: curl -fsSL https://antigravity.google/cli/install.sh | bash"

    if not Path(directory).is_dir():
        return f"Error: Directory does not exist: {directory}"

    if not files_list:
        return "Error: No files provided for file attachment mode"

    mode_normalized = mode.lower()
    if mode_normalized not in {"inline", "at_command"}:
        return f"Error: Unsupported files mode '{mode}'. Use 'inline' or 'at_command'."

    timeout = config.coerce_timeout(timeout_seconds)
    warnings: list[str]

    if mode_normalized == "inline":
        inline_payload, warnings = files.prepare_inline_payload(directory, files_list)
        combined = "\n\n".join([p for p in [inline_payload, query] if p])
    else:
        at_prompt, warnings = files.prepare_at_command_prompt(directory, files_list)
        combined = "\n\n".join([p for p in [at_prompt, query] if p])

    cmd = _build_base_cmd()
    cmd.extend(["--add-dir", directory, "--print", combined])

    success, output, _ = _run_agy(cmd, directory, timeout)

    if warnings:
        warning_block = "Warnings:\n" + "\n".join(f"- {w}" for w in warnings)
        return f"{warning_block}\n\n{output}"
    return output
