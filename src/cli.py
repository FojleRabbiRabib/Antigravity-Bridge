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
import os
import re
import shutil
import signal
import time
from collections.abc import Coroutine
from dataclasses import dataclass, field
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
    # Set on the timeout return paths so metrics don't have to guess from text.
    timed_out: bool = False


@dataclass
class AgyOutcome:
    """Structured result of a public agy call.

    ``success`` distinguishes a real model response from any preflight/runtime
    error (workspace, health, auth, timeout, non-zero exit). ``output`` always
    holds the human-readable text — the response on success, the error message
    otherwise — so existing string callers keep working via ``.output``.
    """

    success: bool
    output: str
    warnings: list[str] = field(default_factory=list)
    model: str = ""
    duration_ms: float | None = None


def _record(
    request_id: str, start: float, result: _ExecResult, *, tool: str, model: str
) -> None:
    """Emit a structured metric record for an agy invocation."""
    duration_ms = round((time.monotonic() - start) * 1000.0, 2)
    observability.record_call(
        request_id=request_id,
        duration_ms=duration_ms,
        success=result.success,
        timed_out=result.timed_out,
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
    *,
    use_pty: bool = False,
) -> _ExecResult:
    """Run ``agy`` with bounded retry on transient failures.

    Authentication errors and non-transient errors are returned immediately.
    Exponential backoff is applied between retries (``base * 2**attempt``).
    """
    attempt = 0
    while True:
        result = await _run_agy_async(cmd, cwd, timeout, use_pty=use_pty)
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


# ---------------------------------------------------------------------------
# PTY-backed execution (works around agy upstream bug #318: ``--print`` hangs
# in non-TTY/headless subprocess environments). agy only emits its response
# when stdin/stdout/stderr are a real terminal, so we allocate a pseudo-TTY,
# hand the slave end to the child, and read the (merged) stream from master.
# ---------------------------------------------------------------------------

# Strips CSI/OSC/other escape sequences agy may emit when it believes it has a
# color terminal, plus stray carriage returns the PTY line discipline adds.
_ANSI_RE = re.compile(
    rb"\x1b\][^\x07]*(\x07|\x1b\\)|\x1b[@-Z\\-_]|\x1b\[[0-?]*[ -/]*[@-~]"
)

# Discourage color/TUI rendering inside the PTY. agy still sees a TTY (so #318
# doesn't trip), but keeps its output plain.
_PTY_ENV = {
    "TERM": "dumb",
    "NO_COLOR": "1",
    "COLUMNS": "200",
    "LINES": "100",
}

# Upper bound on the final proc.wait() in the PTY teardown path, so a killpg
# that fails to actually reap the child cannot hang a cancelling task forever.
_PTY_REAP_TIMEOUT: float = 5.0


def _timeout_message(timeout: int) -> str:
    return (
        f"Error: Antigravity CLI command timed out after {timeout} "
        "seconds. Try increasing timeout or simplifying your query."
    )


def _normalize_pty_output(data: bytes) -> str:
    """Decode PTY bytes, strip ANSI escapes, and drop PTY-added CRs."""
    cleaned = _ANSI_RE.sub(b"", data)
    text = cleaned.decode("utf-8", errors="replace")
    return text.replace("\r\n", "\n").replace("\r", "")


async def _read_fd_all(fd: int) -> bytes:
    """Read ``fd`` to EOF asynchronously.

    On Linux a PTY master raises ``OSError(EIO)`` once the slave side is closed
    (i.e. the child has exited); that is treated as a clean end-of-stream.
    """
    loop = asyncio.get_running_loop()
    chunks: list[bytes] = []
    while True:
        try:
            chunk = await loop.run_in_executor(None, os.read, fd, 65536)
        except OSError:
            break
        if not chunk:
            break
        chunks.append(chunk)
    return b"".join(chunks)


def _terminate_process_group(proc: asyncio.subprocess.Process | None) -> None:
    """Forcefully tear down the child and any descendants it spawned."""
    if proc is None or proc.returncode is not None:
        return
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError) as exc:
        # killpg is the only way to reap descendants the child spawned; if it is
        # denied (e.g. the child dropped privileges / re-setsid'd), fall back to
        # killing just the direct child and log that descendants may survive.
        logger.debug("killpg failed (%s); falling back to proc.kill()", exc)
        with contextlib.suppress(ProcessLookupError):
            proc.kill()


async def _run_agy_pty(cmd: list[str], cwd: str, timeout: int) -> _ExecResult:
    """Run ``agy`` under a pseudo-TTY (merged stdout/stderr) with timeout.

    Used for ``--print`` invocations to dodge upstream bug #318. The combined
    stream is returned as ``output``; ``stderr`` is left empty because a PTY
    cannot separate the two.
    """
    try:
        import pty  # lazy: Unix-only module, absent on Windows
    except ImportError:
        return _ExecResult(
            False,
            "Error: pseudo-TTY support is unavailable on this platform. "
            "Set ANTIGRAVITY_BRIDGE_FORCE_TTY=false to run without a PTY.",
            "",
        )
    try:
        master_fd, slave_fd = pty.openpty()
    except (OSError, ValueError) as exc:
        return _ExecResult(False, f"Error allocating pseudo-TTY: {exc}", "")

    env = {**os.environ, **_PTY_ENV}
    proc: asyncio.subprocess.Process | None = None
    # One try/finally wraps spawn + read so master_fd is released on EVERY path
    # — including spawn failure, whose early returns previously skipped the
    # cleanup below and leaked one fd per failed spawn.
    try:
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=cwd,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                start_new_session=True,
                env=env,
            )
        except FileNotFoundError:
            return _ExecResult(False, AGY_INSTALL_HINT, "")
        except NotADirectoryError:
            return _ExecResult(False, f"Error: Directory does not exist: {cwd}", "")
        except OSError as exc:
            return _ExecResult(False, f"Error launching Antigravity CLI: {exc}", "")
        finally:
            # The child owns its copy of the slave; the parent must release its
            # own so reading master yields EOF once the child exits.
            with contextlib.suppress(OSError):
                os.close(slave_fd)

        try:
            data = await asyncio.wait_for(_read_fd_all(master_fd), timeout=timeout)
            await asyncio.wait_for(proc.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            _terminate_process_group(proc)
            with contextlib.suppress(Exception):
                await proc.wait()
            return _ExecResult(False, _timeout_message(timeout), "", True)
        except asyncio.CancelledError:
            _terminate_process_group(proc)
            with contextlib.suppress(Exception):
                await proc.wait()
            raise
    finally:
        with contextlib.suppress(OSError):
            os.close(master_fd)
        _terminate_process_group(proc)
        # Bounded reap so a failed killpg (exotic: PID reuse / double-setsid)
        # cannot hang the cancelling task indefinitely inside this finally.
        if proc is not None and proc.returncode is None:
            with contextlib.suppress(asyncio.CancelledError, asyncio.TimeoutError):
                await asyncio.wait_for(proc.wait(), timeout=_PTY_REAP_TIMEOUT)

    text = _normalize_pty_output(data).strip()
    returncode = proc.returncode if proc is not None else 0
    if returncode == 0:
        output = text if text else "No output from Antigravity CLI"
        return _ExecResult(True, output, "")
    error_msg = text or f"Exit code {returncode}"
    if _is_auth_error(error_msg):
        return _ExecResult(
            False,
            f"Antigravity CLI Error: Authentication required. Details: {error_msg}",
            "",
        )
    return _ExecResult(False, f"Antigravity CLI Error: {error_msg}", "")


async def _run_agy_async(
    cmd: list[str], cwd: str, timeout: int, *, use_pty: bool = False
) -> _ExecResult:
    """Execute an ``agy`` command asynchronously with timeout + error mapping.

    ``use_pty=True`` routes the call through a pseudo-TTY (needed for
    ``--print`` mode per upstream bug #318); the default pipe path is used for
    subcommands such as ``models`` / ``--version`` that work headless.
    """
    if use_pty:
        return await _run_agy_pty(cmd, cwd, timeout)
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
            return _ExecResult(False, _timeout_message(timeout), "", True)
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
    """Backward-compatible string return (delegates to the outcome variant)."""
    return (
        await execute_antigravity_simple_outcome_async(
            query,
            directory,
            timeout_seconds,
            model,
            add_dirs,
            conversation_id,
            continue_last,
        )
    ).output


async def execute_antigravity_simple_outcome_async(
    query: str,
    directory: str = ".",
    timeout_seconds: int | None = None,
    model: str = "",
    add_dirs: tuple[str, ...] = (),
    conversation_id: str = "",
    continue_last: bool = False,
) -> AgyOutcome:
    """Run a simple query and return a structured :class:`AgyOutcome`."""
    err = _check_workspace(directory, add_dirs=add_dirs)
    if err:
        return AgyOutcome(success=False, output=err, model=model)

    settings = config.load_settings()
    if settings.health_check and not await ensure_healthy():
        return AgyOutcome(success=False, output=HEALTH_FAILED_HINT, model=model)
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
    result = await _run_with_retry(
        cmd, directory, timeout, settings, request_id, use_pty=settings.force_tty
    )
    used_model = model or settings.model
    _record(request_id, start, result, tool="agy_consult", model=used_model)
    return AgyOutcome(
        success=result.success,
        output=result.output,
        model=used_model,
        duration_ms=round((time.monotonic() - start) * 1000.0, 2),
    )


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
    """Backward-compatible string return (delegates to the outcome variant)."""
    return (
        await execute_antigravity_with_files_outcome_async(
            query,
            directory,
            files_list,
            timeout_seconds,
            mode,
            model,
            add_dirs,
            conversation_id,
            continue_last,
        )
    ).output


async def execute_antigravity_with_files_outcome_async(
    query: str,
    directory: str = ".",
    files_list: list[str] | None = None,
    timeout_seconds: int | None = None,
    mode: str = "inline",
    model: str = "",
    add_dirs: tuple[str, ...] = (),
    conversation_id: str = "",
    continue_last: bool = False,
) -> AgyOutcome:
    """Run a file-context query and return a structured :class:`AgyOutcome`."""
    err = _check_workspace(directory, add_dirs=add_dirs)
    if err:
        return AgyOutcome(success=False, output=err, model=model)

    if not files_list:
        return AgyOutcome(
            success=False,
            output="Error: No files provided for file attachment mode",
            model=model,
        )

    mode_normalized = mode.lower()
    if mode_normalized not in {"inline", "at_command"}:
        return AgyOutcome(
            success=False,
            output=f"Error: Unsupported files mode '{mode}'. Use 'inline' or 'at_command'.",
            model=model,
        )

    settings = config.load_settings()
    if settings.health_check and not await ensure_healthy():
        return AgyOutcome(success=False, output=HEALTH_FAILED_HINT, model=model)
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
    result = await _run_with_retry(
        cmd, directory, timeout, settings, request_id, use_pty=settings.force_tty
    )
    used_model = model or settings.model
    _record(
        request_id,
        start,
        result,
        tool="agy_consult_with_files",
        model=used_model,
    )

    if warnings:
        warning_block = "Warnings:\n" + "\n".join(f"- {w}" for w in warnings)
        output = f"{warning_block}\n\n{result.output}"
    else:
        output = result.output
    return AgyOutcome(
        success=result.success,
        output=output,
        warnings=list(warnings),
        model=used_model,
        duration_ms=round((time.monotonic() - start) * 1000.0, 2),
    )


async def execute_antigravity_models_async() -> str:
    """Backward-compatible string return (delegates to the outcome variant)."""
    return (await execute_antigravity_models_outcome_async()).output


async def execute_antigravity_models_outcome_async() -> AgyOutcome:
    """List available models via the ``agy models`` subcommand."""
    if not shutil.which("agy"):
        return AgyOutcome(success=False, output=AGY_INSTALL_HINT)
    settings = config.load_settings()
    if settings.health_check and not await ensure_healthy():
        return AgyOutcome(success=False, output=HEALTH_FAILED_HINT)
    cmd: list[str] = ["agy"]
    if settings.skip_permissions:
        cmd.append("--dangerously-skip-permissions")
    cmd.append("models")
    timeout = config.coerce_timeout(None)
    request_id = observability.new_request_id()
    start = time.monotonic()
    # ``agy models`` is a plain subcommand that works headless; no PTY needed.
    result = await _run_with_retry(cmd, ".", timeout, settings, request_id)
    _record(request_id, start, result, tool="agy_list_models", model="")
    return AgyOutcome(
        success=result.success,
        output=result.output,
        duration_ms=round((time.monotonic() - start) * 1000.0, 2),
    )


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
