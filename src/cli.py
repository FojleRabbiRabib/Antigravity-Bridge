"""Antigravity Bridge CLI interaction — async subprocess calls to ``agy``.

The execution core is async (``asyncio.create_subprocess_exec``) so MCP tools do
not block the event loop. Sync wrappers (:func:`execute_antigravity_simple` and
:func:`execute_antigravity_with_files`) preserve the historical public API by
running the async core via :func:`asyncio.run`.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import shutil
import time
from collections.abc import Coroutine
from pathlib import Path
from typing import Any, NamedTuple

from . import config, files, observability, security
from .command import AgyCommand

logger = logging.getLogger(__name__)

AGY_INSTALL_HINT = (
    "Error: Antigravity CLI not found. "
    "Install with: curl -fsSL https://antigravity.google/cli/install.sh | bash"
)

HEALTH_FAILED_HINT = (
    "Error: Antigravity CLI health check failed. "
    "Verify agy is installed and authenticated."
)

# Cached result of the one-time agy --version probe. Only success is cached;
# failures are re-checked so the server recovers if agy becomes healthy later.
_health_cache: bool | None = None

# Serializes concurrent health probes so a cold start does not stampede agy with
# parallel ``--version`` invocations (thundering-herd guard).
_health_lock = asyncio.Lock()

_AUTH_MARKERS = ("authentication", "auth", "unauthorized", "login", "credential")
_TRANSIENT_MARKERS = (
    "connection",
    "network",
    "timeout",
    "timed out",
    "eof",
    "reset",
    "temporary",
    "retry",
    "unavailable",
)


class _ExecResult(NamedTuple):
    success: bool
    output: str
    stderr: str


def _record(
    request_id: str, start: float, result: _ExecResult, *, tool: str, model: str
) -> None:
    """Emit a structured metric record for an agy invocation."""
    duration_ms = round((time.monotonic() - start) * 1000.0, 2)
    observability.record_call(
        request_id=request_id,
        duration_ms=duration_ms,
        success=result.success,
        timed_out=("timed out" in result.output.lower()),
        tool=tool,
        model=model or "",
    )


def _is_auth_error(message: str) -> bool:
    low = message.lower()
    return any(marker in low for marker in _AUTH_MARKERS)


def is_transient_error(message: str) -> bool:
    """Whether an error message looks like a retryable/transient failure."""
    low = message.lower()
    return any(marker in low for marker in _TRANSIENT_MARKERS)


async def _run_with_retry(
    cmd: list[str],
    cwd: str,
    timeout: int,
    settings: config.Settings,
    request_id: str = "",
) -> _ExecResult:
    """Run ``agy`` with bounded retry on transient failures.

    Authentication errors and non-transient errors are returned immediately.
    Exponential backoff is applied between retries (``base * 2**attempt``).
    """
    attempt = 0
    while True:
        result = await _run_agy_async(cmd, cwd, timeout)
        if result.success:
            return result
        if _is_auth_error(result.output):
            return result
        if attempt >= settings.max_retries:
            return result
        if not is_transient_error(result.output):
            return result
        backoff = settings.retry_backoff_base * (2**attempt)
        logger.warning(
            "agy attempt %d failed (transient); retrying in %.2fs: %s",
            attempt + 1,
            backoff,
            result.output,
        )
        observability.get_logger().debug(
            "retry scheduled",
            extra={
                "event": "agy.retry",
                "request_id": request_id,
                "attempt": attempt + 1,
                "backoff_s": backoff,
            },
        )
        await asyncio.sleep(backoff)
        attempt += 1


async def _run_agy_async(cmd: list[str], cwd: str, timeout: int) -> _ExecResult:
    """Execute an ``agy`` command asynchronously with timeout + error mapping."""
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.DEVNULL,
        )
    except FileNotFoundError:
        return _ExecResult(False, AGY_INSTALL_HINT, "")
    except NotADirectoryError:
        return _ExecResult(False, f"Error: Directory does not exist: {cwd}", "")
    except OSError as exc:
        return _ExecResult(False, f"Error launching Antigravity CLI: {exc}", "")

    try:
        try:
            stdout_b, stderr_b = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            with contextlib.suppress(ProcessLookupError):
                proc.kill()
            await proc.wait()
            return _ExecResult(
                False,
                (
                    f"Error: Antigravity CLI command timed out after {timeout} "
                    "seconds. Try increasing timeout or simplifying your query."
                ),
                "",
            )
    finally:
        # Ensure the subprocess is never orphaned. Covers cancellation
        # (CancelledError propagated out of communicate) and any other early
        # exit while the process is still alive.
        if proc.returncode is None:
            with contextlib.suppress(ProcessLookupError):
                proc.kill()
            with contextlib.suppress(asyncio.CancelledError):
                await proc.wait()

    stdout = stdout_b.decode("utf-8", errors="replace") if stdout_b else ""
    stderr = stderr_b.decode("utf-8", errors="replace") if stderr_b else ""

    if proc.returncode == 0:
        if stderr.strip():
            logger.debug("agy emitted stderr on success: %s", stderr.strip())
        output = stdout.strip() if stdout.strip() else "No output from Antigravity CLI"
        return _ExecResult(True, output, stderr)

    error_msg = stderr.strip() or f"Exit code {proc.returncode}"
    if stdout.strip():
        logger.debug("agy stdout on failure: %s", stdout.strip())
    if _is_auth_error(error_msg):
        return _ExecResult(
            False,
            f"Antigravity CLI Error: Authentication required. Details: {error_msg}",
            stderr,
        )
    return _ExecResult(False, f"Antigravity CLI Error: {error_msg}", stderr)


def _check_workspace(directory: str, add_dirs: tuple[str, ...] = ()) -> str | None:
    """Return an error string if the workspace is unusable, else None.

    Both the working ``directory`` and every entry in ``add_dirs`` are
    existence-checked and run against the configured allowlist. ``add_dirs``
    entries bypassing the allowlist was a former escape vector.
    """
    if not shutil.which("agy"):
        return AGY_INSTALL_HINT
    if not Path(directory).is_dir():
        return f"Error: Directory does not exist: {directory}"
    allowed_dirs = config.load_settings().allowed_dirs
    try:
        security.check_allowed_directory(directory, allowed_dirs)
    except security.SecurityError as exc:
        return f"Error: {exc}"
    for extra in add_dirs:
        if not Path(extra).is_dir():
            return f"Error: Directory does not exist: {extra}"
        try:
            security.check_allowed_directory(extra, allowed_dirs)
        except security.SecurityError as exc:
            return f"Error: {exc}"
    return None


def reset_health_cache() -> None:
    """Clear the cached agy health-check result (mainly for tests)."""
    global _health_cache
    _health_cache = None


async def ensure_healthy() -> bool:
    """One-time ``agy --version`` probe; success is cached for the process."""
    global _health_cache
    if _health_cache:
        return True
    async with _health_lock:
        # Re-check inside the lock: a racing coroutine may have populated the
        # cache while we were waiting.
        if _health_cache:
            return True
        if not shutil.which("agy"):
            return False
        try:
            proc = await asyncio.create_subprocess_exec(
                "agy",
                "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.communicate(), timeout=10)
        except asyncio.TimeoutError:
            # The timed-out subprocess is still alive — reap it to avoid leaks.
            # NOTE: this must precede the OSError handler. On Python 3.11+
            # asyncio.TimeoutError aliases the builtin TimeoutError, which is a
            # subclass of OSError, so a broader OSError handler would otherwise
            # swallow the timeout and leak the probe process.
            logger.debug("agy health check timed out; killing probe process")
            with contextlib.suppress(ProcessLookupError):
                proc.kill()
            await proc.wait()
            return False
        except (FileNotFoundError, OSError) as exc:
            logger.debug("agy health check failed: %s", exc)
            return False
        healthy = proc.returncode == 0
        if healthy:
            _health_cache = True
            logger.info("agy health check passed")
        else:
            logger.warning("agy health check failed (exit %s)", proc.returncode)
        return healthy


def _build_command(
    *,
    query: str,
    directory: str,
    timeout: int,
    settings: config.Settings,
    model: str = "",
    add_dirs: tuple[str, ...] = (),
    conversation_id: str = "",
    continue_last: bool = False,
) -> list[str]:
    return AgyCommand(
        query=query,
        directory=directory,
        timeout=timeout,
        model=model or settings.model,
        add_dirs=add_dirs,
        skip_permissions=settings.skip_permissions,
        sandbox=settings.sandbox,
        conversation_id=conversation_id,
        continue_last=continue_last,
        align_print_timeout=settings.align_print_timeout,
    ).build()


async def execute_antigravity_simple_async(
    query: str,
    directory: str = ".",
    timeout_seconds: int | None = None,
    model: str = "",
    add_dirs: tuple[str, ...] = (),
    conversation_id: str = "",
    continue_last: bool = False,
) -> str:
    err = _check_workspace(directory, add_dirs=add_dirs)
    if err:
        return err

    settings = config.load_settings()
    if settings.health_check and not await ensure_healthy():
        return HEALTH_FAILED_HINT
    timeout = config.coerce_timeout(timeout_seconds)
    cmd = _build_command(
        query=query,
        directory=directory,
        timeout=timeout,
        settings=settings,
        model=model,
        add_dirs=add_dirs,
        conversation_id=conversation_id,
        continue_last=continue_last,
    )
    request_id = observability.new_request_id()
    start = time.monotonic()
    result = await _run_with_retry(cmd, directory, timeout, settings, request_id)
    _record(
        request_id, start, result, tool="agy_consult", model=model or settings.model
    )
    return result.output


async def execute_antigravity_with_files_async(
    query: str,
    directory: str = ".",
    files_list: list[str] | None = None,
    timeout_seconds: int | None = None,
    mode: str = "inline",
    model: str = "",
    add_dirs: tuple[str, ...] = (),
    conversation_id: str = "",
    continue_last: bool = False,
) -> str:
    err = _check_workspace(directory, add_dirs=add_dirs)
    if err:
        return err

    if not files_list:
        return "Error: No files provided for file attachment mode"

    mode_normalized = mode.lower()
    if mode_normalized not in {"inline", "at_command"}:
        return f"Error: Unsupported files mode '{mode}'. Use 'inline' or 'at_command'."

    settings = config.load_settings()
    if settings.health_check and not await ensure_healthy():
        return HEALTH_FAILED_HINT
    timeout = config.coerce_timeout(timeout_seconds)

    if mode_normalized == "inline":
        inline_payload, warnings = files.prepare_inline_payload(directory, files_list)
        combined = "\n\n".join([p for p in [inline_payload, query] if p])
    else:
        at_prompt, warnings = files.prepare_at_command_prompt(directory, files_list)
        combined = "\n\n".join([p for p in [at_prompt, query] if p])

    cmd = _build_command(
        query=combined,
        directory=directory,
        timeout=timeout,
        settings=settings,
        model=model,
        add_dirs=add_dirs,
        conversation_id=conversation_id,
        continue_last=continue_last,
    )
    request_id = observability.new_request_id()
    start = time.monotonic()
    result = await _run_with_retry(cmd, directory, timeout, settings, request_id)
    _record(
        request_id,
        start,
        result,
        tool="agy_consult_with_files",
        model=model or settings.model,
    )

    if warnings:
        warning_block = "Warnings:\n" + "\n".join(f"- {w}" for w in warnings)
        return f"{warning_block}\n\n{result.output}"
    return result.output


async def execute_antigravity_models_async() -> str:
    """List available models via the ``agy models`` subcommand."""
    if not shutil.which("agy"):
        return AGY_INSTALL_HINT
    settings = config.load_settings()
    if settings.health_check and not await ensure_healthy():
        return HEALTH_FAILED_HINT
    cmd: list[str] = ["agy"]
    if settings.skip_permissions:
        cmd.append("--dangerously-skip-permissions")
    cmd.append("models")
    timeout = config.coerce_timeout(None)
    request_id = observability.new_request_id()
    start = time.monotonic()
    result = await _run_with_retry(cmd, ".", timeout, settings, request_id)
    _record(request_id, start, result, tool="agy_list_models", model="")
    return result.output


def execute_antigravity_simple(
    query: str,
    directory: str = ".",
    timeout_seconds: int | None = None,
    model: str = "",
    add_dirs: tuple[str, ...] | list[str] = (),
    conversation_id: str = "",
    continue_last: bool = False,
) -> str:
    """Sync wrapper around :func:`execute_antigravity_simple_async`."""
    return _run_sync(
        execute_antigravity_simple_async(
            query,
            directory,
            timeout_seconds,
            model,
            tuple(add_dirs),
            conversation_id,
            continue_last,
        )
    )


def execute_antigravity_with_files(
    query: str,
    directory: str = ".",
    files_list: list[str] | None = None,
    timeout_seconds: int | None = None,
    mode: str = "inline",
    model: str = "",
    add_dirs: tuple[str, ...] | list[str] = (),
    conversation_id: str = "",
    continue_last: bool = False,
) -> str:
    """Sync wrapper around :func:`execute_antigravity_with_files_async`."""
    return _run_sync(
        execute_antigravity_with_files_async(
            query,
            directory,
            files_list,
            timeout_seconds,
            mode,
            model,
            tuple(add_dirs),
            conversation_id,
            continue_last,
        )
    )


def _run_sync(coro: Coroutine[Any, Any, str]) -> str:
    """Run a coroutine to completion from sync context.

    Robust to being called from within a running event loop (e.g. a sync tool
    invoked via a threadpool) by delegating to a worker thread.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    # A loop is already running in this thread — execute off-loop in a worker.
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()
