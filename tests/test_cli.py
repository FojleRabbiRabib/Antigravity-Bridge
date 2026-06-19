import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeProc:
    def __init__(self, returncode=0, stdout=b"Answer\n", stderr=b""):
        self.returncode = returncode
        self._stdout = stdout
        self._stderr = stderr
        self.killed = False
        self.pid = 12345

    async def communicate(self):
        return self._stdout, self._stderr

    async def wait(self):
        return self.returncode

    def kill(self):
        self.killed = True


class _TimeoutProc(_FakeProc):
    async def communicate(self):
        raise asyncio.TimeoutError()


def _patch_exec(monkeypatch, proc, capture=None):
    async def fake_exec(*args, **kwargs):
        if capture is not None:
            capture["cmd"] = list(args)
            capture["cwd"] = kwargs.get("cwd")
        return proc

    monkeypatch.setattr("src.cli.asyncio.create_subprocess_exec", fake_exec)


@pytest.fixture(autouse=True)
def clear_env_vars(monkeypatch):
    for v in [
        "ANTIGRAVITY_BRIDGE_TIMEOUT",
        "ANTIGRAVITY_BRIDGE_DEFAULT_TIMEOUT",
        "ANTIGRAVITY_BRIDGE_SKIP_PERMISSIONS",
        "ANTIGRAVITY_BRIDGE_SANDBOX",
        "ANTIGRAVITY_BRIDGE_MODEL",
        "ANTIGRAVITY_BRIDGE_ALLOWED_DIRS",
        "ANTIGRAVITY_BRIDGE_HEALTH_CHECK",
        "ANTIGRAVITY_BRIDGE_ALIGN_PRINT_TIMEOUT",
        "ANTIGRAVITY_BRIDGE_MAX_RETRIES",
    ]:
        monkeypatch.delenv(v, raising=False)
    # Keep execute tests isolated from the cached health probe.
    import src.cli as cli

    cli.reset_health_cache()
    monkeypatch.setenv("ANTIGRAVITY_BRIDGE_HEALTH_CHECK", "false")
    # Legacy tests assert against the pipe-based ``communicate()`` path via
    # ``_FakeProc``; route them off the PTY path. Dedicated tests cover PTY.
    monkeypatch.setenv("ANTIGRAVITY_BRIDGE_FORCE_TTY", "false")


# ---------------------------------------------------------------------------
# simple (async + sync wrapper)
# ---------------------------------------------------------------------------


async def test_async_not_found(tmp_path, monkeypatch):
    import src.cli as cli

    monkeypatch.setattr(cli.shutil, "which", lambda _: None)
    out = await cli.execute_antigravity_simple_async("Hi", str(tmp_path))
    assert "Antigravity CLI not found" in out


async def test_async_invalid_directory(monkeypatch):
    import src.cli as cli

    monkeypatch.setattr(cli.shutil, "which", lambda _: "agy")
    out = await cli.execute_antigravity_simple_async("Hi", "non-existent-path")
    assert "Directory does not exist" in out


async def test_async_success(tmp_path, monkeypatch):
    import src.cli as cli

    monkeypatch.setattr(cli.shutil, "which", lambda _: "agy")
    cap = {}
    _patch_exec(monkeypatch, _FakeProc(0, b"Answer\n", b""), cap)
    out = await cli.execute_antigravity_simple_async("Hi", str(tmp_path))
    assert out == "Answer"
    assert "agy" in cap["cmd"]
    assert "--print" in cap["cmd"]


async def test_async_passes_print_timeout_aligned(tmp_path, monkeypatch):
    import src.cli as cli

    monkeypatch.setattr(cli.shutil, "which", lambda _: "agy")
    cap = {}
    _patch_exec(monkeypatch, _FakeProc(), cap)
    await cli.execute_antigravity_simple_async("Hi", str(tmp_path), timeout_seconds=42)
    assert "--print-timeout" in cap["cmd"]
    i = cap["cmd"].index("--print-timeout")
    assert cap["cmd"][i + 1] == "42s"


async def test_async_disable_align_print_timeout(tmp_path, monkeypatch):
    import src.cli as cli

    monkeypatch.setattr(cli.shutil, "which", lambda _: "agy")
    monkeypatch.setenv("ANTIGRAVITY_BRIDGE_ALIGN_PRINT_TIMEOUT", "false")
    cap = {}
    _patch_exec(monkeypatch, _FakeProc(), cap)
    await cli.execute_antigravity_simple_async("Hi", str(tmp_path))
    assert "--print-timeout" not in cap["cmd"]


async def test_async_skip_permissions(tmp_path, monkeypatch):
    import src.cli as cli

    monkeypatch.setattr(cli.shutil, "which", lambda _: "agy")
    monkeypatch.setenv("ANTIGRAVITY_BRIDGE_SKIP_PERMISSIONS", "true")
    cap = {}
    _patch_exec(monkeypatch, _FakeProc(), cap)
    await cli.execute_antigravity_simple_async("Hi", str(tmp_path))
    assert "--dangerously-skip-permissions" in cap["cmd"]


async def test_async_sandbox(tmp_path, monkeypatch):
    import src.cli as cli

    monkeypatch.setattr(cli.shutil, "which", lambda _: "agy")
    monkeypatch.setenv("ANTIGRAVITY_BRIDGE_SANDBOX", "true")
    cap = {}
    _patch_exec(monkeypatch, _FakeProc(), cap)
    await cli.execute_antigravity_simple_async("Hi", str(tmp_path))
    assert "--sandbox" in cap["cmd"]


async def test_async_model(tmp_path, monkeypatch):
    import src.cli as cli

    monkeypatch.setattr(cli.shutil, "which", lambda _: "agy")
    cap = {}
    _patch_exec(monkeypatch, _FakeProc(), cap)
    await cli.execute_antigravity_simple_async(
        "Hi", str(tmp_path), model="gemini-3.5-flash"
    )
    assert "--model" in cap["cmd"]
    i = cap["cmd"].index("--model")
    assert cap["cmd"][i + 1] == "gemini-3.5-flash"


async def test_async_extra_dirs(tmp_path, monkeypatch):
    import src.cli as cli

    extra = tmp_path / "extra"
    extra.mkdir()
    monkeypatch.setattr(cli.shutil, "which", lambda _: "agy")
    cap = {}
    _patch_exec(monkeypatch, _FakeProc(), cap)
    await cli.execute_antigravity_simple_async(
        "Hi", str(tmp_path), add_dirs=(str(extra),)
    )
    assert cap["cmd"].count("--add-dir") == 2


async def test_async_conversation_id(tmp_path, monkeypatch):
    import src.cli as cli

    monkeypatch.setattr(cli.shutil, "which", lambda _: "agy")
    cap = {}
    _patch_exec(monkeypatch, _FakeProc(), cap)
    await cli.execute_antigravity_simple_async(
        "Hi", str(tmp_path), conversation_id="abc-123"
    )
    assert "--conversation" in cap["cmd"]
    assert "abc-123" in cap["cmd"]


async def test_async_auth_error(tmp_path, monkeypatch):
    import src.cli as cli

    monkeypatch.setattr(cli.shutil, "which", lambda _: "agy")
    _patch_exec(monkeypatch, _FakeProc(1, b"", b"Authentication required"))
    out = await cli.execute_antigravity_simple_async("Hi", str(tmp_path))
    assert "Authentication required" in out


async def test_async_generic_error(tmp_path, monkeypatch):
    import src.cli as cli

    monkeypatch.setattr(cli.shutil, "which", lambda _: "agy")
    _patch_exec(monkeypatch, _FakeProc(2, b"", b"something went wrong"))
    out = await cli.execute_antigravity_simple_async("Hi", str(tmp_path))
    assert "Antigravity CLI Error: something went wrong" in out


async def test_async_empty_output(tmp_path, monkeypatch):
    import src.cli as cli

    monkeypatch.setattr(cli.shutil, "which", lambda _: "agy")
    _patch_exec(monkeypatch, _FakeProc(0, b"", b""))
    out = await cli.execute_antigravity_simple_async("Hi", str(tmp_path))
    assert "No output from Antigravity CLI" in out


async def test_async_timeout(tmp_path, monkeypatch):
    import src.cli as cli

    monkeypatch.setattr(cli.shutil, "which", lambda _: "agy")
    proc = _TimeoutProc()
    _patch_exec(monkeypatch, proc)
    out = await cli.execute_antigravity_simple_async(
        "Hi", str(tmp_path), timeout_seconds=5
    )
    assert "timed out" in out
    assert proc.killed is True


async def test_async_allowlist_blocks(tmp_path, monkeypatch):
    import src.cli as cli

    allowed = tmp_path / "allowed"
    allowed.mkdir()
    other = tmp_path / "other"
    other.mkdir()
    monkeypatch.setattr(cli.shutil, "which", lambda _: "agy")
    monkeypatch.setenv("ANTIGRAVITY_BRIDGE_ALLOWED_DIRS", str(allowed))
    out = await cli.execute_antigravity_simple_async("Hi", str(other))
    assert "not in allowlist" in out.lower()


async def test_sync_wrapper_runs(tmp_path, monkeypatch):
    import src.cli as cli

    monkeypatch.setattr(cli.shutil, "which", lambda _: "agy")
    _patch_exec(monkeypatch, _FakeProc(0, b"OK\n", b""))
    out = cli.execute_antigravity_simple("Hi", str(tmp_path))
    assert out == "OK"


# ---------------------------------------------------------------------------
# health preflight
# ---------------------------------------------------------------------------


async def test_health_probe_caches_success(monkeypatch):
    import src.cli as cli

    cli.reset_health_cache()
    monkeypatch.setattr(cli.shutil, "which", lambda _: "agy")
    calls = []

    async def fake_exec(*args, **kwargs):
        calls.append(args)
        return _FakeProc(0, b"agy 1.2.3\n", b"")

    monkeypatch.setattr(cli.asyncio, "create_subprocess_exec", fake_exec)
    assert await cli.ensure_healthy() is True
    assert await cli.ensure_healthy() is True
    assert len(calls) == 1  # cached after first success


async def test_health_probe_failure_not_cached(monkeypatch):
    import src.cli as cli

    cli.reset_health_cache()
    monkeypatch.setattr(cli.shutil, "which", lambda _: "agy")

    async def fake_exec(*args, **kwargs):
        return _FakeProc(1, b"", b"broken")

    monkeypatch.setattr(cli.asyncio, "create_subprocess_exec", fake_exec)
    assert await cli.ensure_healthy() is False


async def test_health_probe_missing_binary(monkeypatch):
    import src.cli as cli

    cli.reset_health_cache()
    monkeypatch.setattr(cli.shutil, "which", lambda _: None)
    assert await cli.ensure_healthy() is False


async def test_execute_blocks_when_unhealthy(tmp_path, monkeypatch):
    import src.cli as cli

    cli.reset_health_cache()
    monkeypatch.setattr(cli.shutil, "which", lambda _: "agy")
    monkeypatch.setenv("ANTIGRAVITY_BRIDGE_HEALTH_CHECK", "true")
    monkeypatch.setattr(cli, "ensure_healthy", _async_value(False))
    out = await cli.execute_antigravity_simple_async("Hi", str(tmp_path))
    assert "health check failed" in out.lower()


async def test_execute_proceeds_when_healthy(tmp_path, monkeypatch):
    import src.cli as cli

    cli.reset_health_cache()
    monkeypatch.setattr(cli.shutil, "which", lambda _: "agy")
    monkeypatch.setenv("ANTIGRAVITY_BRIDGE_HEALTH_CHECK", "true")
    monkeypatch.setattr(cli, "ensure_healthy", _async_value(True))
    _patch_exec(monkeypatch, _FakeProc(0, b"OK\n", b""))
    out = await cli.execute_antigravity_simple_async("Hi", str(tmp_path))
    assert out == "OK"


def _async_value(value):
    async def _fn(*args, **kwargs):
        return value

    return _fn


# ---------------------------------------------------------------------------
# retry with backoff
# ---------------------------------------------------------------------------


async def _noop_sleep(*args, **kwargs):
    return None


async def test_retry_transient_then_success(monkeypatch):
    import src.cli as cli

    settings = cli.config.load_settings()
    calls = []

    async def fake_run(cmd, cwd, timeout, *, use_pty=False):
        calls.append(1)
        if len(calls) == 1:
            return cli._ExecResult(False, "Antigravity CLI Error: connection reset", "")
        return cli._ExecResult(True, "OK", "")

    monkeypatch.setattr(cli, "_run_agy_async", fake_run)
    monkeypatch.setattr(cli.asyncio, "sleep", _noop_sleep)
    result = await cli._run_with_retry(["agy"], ".", 5, settings)
    assert result.success
    assert result.output == "OK"
    assert len(calls) == 2


async def test_retry_skips_auth_errors(monkeypatch):
    import src.cli as cli

    settings = cli.config.load_settings()
    calls = []

    async def fake_run(cmd, cwd, timeout, *, use_pty=False):
        calls.append(1)
        return cli._ExecResult(
            False, "Antigravity CLI Error: Authentication required", ""
        )

    monkeypatch.setattr(cli, "_run_agy_async", fake_run)
    monkeypatch.setattr(cli.asyncio, "sleep", _noop_sleep)
    result = await cli._run_with_retry(["agy"], ".", 5, settings)
    assert not result.success
    assert len(calls) == 1  # never retried


async def test_retry_skips_permanent_errors(monkeypatch):
    import src.cli as cli

    settings = cli.config.load_settings()
    calls = []

    async def fake_run(cmd, cwd, timeout, *, use_pty=False):
        calls.append(1)
        return cli._ExecResult(False, "Antigravity CLI Error: bad syntax", "")

    monkeypatch.setattr(cli, "_run_agy_async", fake_run)
    monkeypatch.setattr(cli.asyncio, "sleep", _noop_sleep)
    await cli._run_with_retry(["agy"], ".", 5, settings)
    assert len(calls) == 1


async def test_retry_caps_at_max(monkeypatch):
    import src.cli as cli

    monkeypatch.setenv("ANTIGRAVITY_BRIDGE_MAX_RETRIES", "1")
    settings = cli.config.load_settings()
    assert settings.max_retries == 1
    calls = []

    async def fake_run(cmd, cwd, timeout, *, use_pty=False):
        calls.append(1)
        return cli._ExecResult(False, "Antigravity CLI Error: network timeout", "")

    monkeypatch.setattr(cli, "_run_agy_async", fake_run)
    monkeypatch.setattr(cli.asyncio, "sleep", _noop_sleep)
    result = await cli._run_with_retry(["agy"], ".", 5, settings)
    assert not result.success
    assert len(calls) == 2  # 1 initial + 1 retry


async def test_retry_zero_retries(monkeypatch):
    import src.cli as cli

    monkeypatch.setenv("ANTIGRAVITY_BRIDGE_MAX_RETRIES", "0")
    settings = cli.config.load_settings()
    calls = []

    async def fake_run(cmd, cwd, timeout, *, use_pty=False):
        calls.append(1)
        return cli._ExecResult(False, "Antigravity CLI Error: connection reset", "")

    monkeypatch.setattr(cli, "_run_agy_async", fake_run)
    monkeypatch.setattr(cli.asyncio, "sleep", _noop_sleep)
    await cli._run_with_retry(["agy"], ".", 5, settings)
    assert len(calls) == 1


# ---------------------------------------------------------------------------
# observability wiring (request id, timing, metrics)
# ---------------------------------------------------------------------------


def _record_spy(monkeypatch):
    import src.cli as cli

    recorded = {}

    def fake_record(**kwargs):
        recorded.update(kwargs)

    monkeypatch.setattr(cli.observability, "record_call", fake_record)
    return recorded


async def test_observability_records_success(tmp_path, monkeypatch):
    import src.cli as cli

    monkeypatch.setattr(cli.shutil, "which", lambda _: "agy")
    _patch_exec(monkeypatch, _FakeProc(0, b"OK\n", b""))
    recorded = _record_spy(monkeypatch)
    await cli.execute_antigravity_simple_async("Hi", str(tmp_path))
    assert recorded.get("success") is True
    assert recorded.get("timed_out") is False
    assert "duration_ms" in recorded
    assert "request_id" in recorded
    assert recorded.get("tool") == "agy_consult"


async def test_observability_records_timeout(tmp_path, monkeypatch):
    import src.cli as cli

    monkeypatch.setattr(cli.shutil, "which", lambda _: "agy")
    _patch_exec(monkeypatch, _TimeoutProc())
    recorded = _record_spy(monkeypatch)
    monkeypatch.setattr(cli.asyncio, "sleep", _noop_sleep)
    await cli.execute_antigravity_simple_async("Hi", str(tmp_path), timeout_seconds=5)
    assert recorded.get("success") is False
    assert recorded.get("timed_out") is True


# ---------------------------------------------------------------------------
# models subcommand
# ---------------------------------------------------------------------------


async def test_models_async_runs_subcommand(tmp_path, monkeypatch):
    import src.cli as cli

    monkeypatch.setattr(cli.shutil, "which", lambda _: "agy")
    cap = {}
    _patch_exec(
        monkeypatch, _FakeProc(0, b"Gemini 3.5 Flash\nClaude Sonnet 4.6\n", b""), cap
    )
    out = await cli.execute_antigravity_models_async()
    assert "Gemini" in out
    assert "models" in cap["cmd"]
    assert "--print" not in cap["cmd"]


async def test_models_async_not_found(monkeypatch):
    import src.cli as cli

    monkeypatch.setattr(cli.shutil, "which", lambda _: None)
    out = await cli.execute_antigravity_models_async()
    assert "Antigravity CLI not found" in out


# ---------------------------------------------------------------------------
# with_files (async)
# ---------------------------------------------------------------------------


async def test_with_files_requires_files(tmp_path, monkeypatch):
    import src.cli as cli

    monkeypatch.setattr(cli.shutil, "which", lambda _: "agy")
    out = await cli.execute_antigravity_with_files_async(
        "Hi", str(tmp_path), files_list=None
    )
    assert "No files provided" in out


async def test_with_files_inline_mode(tmp_path, monkeypatch):
    import src.cli as cli

    monkeypatch.setattr(cli.shutil, "which", lambda _: "agy")
    f = tmp_path / "example.txt"
    f.write_text("content", encoding="utf-8")
    cap = {}
    _patch_exec(monkeypatch, _FakeProc(0, b"ok\n", b""), cap)
    out = await cli.execute_antigravity_with_files_async(
        "Hi", str(tmp_path), files_list=["example.txt"]
    )
    assert out == "ok"
    assert "=== example.txt ===" in " ".join(cap["cmd"])


async def test_with_files_at_command_mode(tmp_path, monkeypatch):
    import src.cli as cli

    monkeypatch.setattr(cli.shutil, "which", lambda _: "agy")
    f = tmp_path / "context" / "info.txt"
    f.parent.mkdir()
    f.write_text("data", encoding="utf-8")
    cap = {}
    _patch_exec(monkeypatch, _FakeProc(0, b"ok\n", b""), cap)
    out = await cli.execute_antigravity_with_files_async(
        "Hi", str(tmp_path), files_list=["context/info.txt"], mode="at_command"
    )
    assert out == "ok"
    assert "@context/info.txt" in " ".join(cap["cmd"])


async def test_with_files_unsupported_mode(tmp_path, monkeypatch):
    import src.cli as cli

    monkeypatch.setattr(cli.shutil, "which", lambda _: "agy")
    f = tmp_path / "test.txt"
    f.write_text("x", encoding="utf-8")
    out = await cli.execute_antigravity_with_files_async(
        "Hi", str(tmp_path), files_list=["test.txt"], mode="bad_mode"
    )
    assert "Unsupported files mode" in out


async def test_with_files_missing_file_warnings(tmp_path, monkeypatch):
    import src.cli as cli

    monkeypatch.setattr(cli.shutil, "which", lambda _: "agy")
    _patch_exec(monkeypatch, _FakeProc(0, b"done\n", b""))
    out = await cli.execute_antigravity_with_files_async(
        "Hi", str(tmp_path), files_list=["missing.txt"]
    )
    assert "Warnings" in out
    assert "Skipped missing file" in out


async def test_with_files_binary_skipped(tmp_path, monkeypatch):
    import src.cli as cli

    monkeypatch.setattr(cli.shutil, "which", lambda _: "agy")
    b = tmp_path / "x.bin"
    b.write_bytes(b"\x00\x01PNG")
    cap = {}
    _patch_exec(monkeypatch, _FakeProc(0, b"ok\n", b""), cap)
    out = await cli.execute_antigravity_with_files_async(
        "Hi", str(tmp_path), files_list=["x.bin"]
    )
    assert "binary" in out.lower()


# ---------------------------------------------------------------------------
# Audit fixes
# ---------------------------------------------------------------------------


class _CancelledProc(_FakeProc):
    def __init__(self):
        # returncode stays None so the reaper path treats the proc as still
        # running and kills it.
        super().__init__(returncode=None)

    async def communicate(self):
        raise asyncio.CancelledError()


async def test_add_dirs_inside_allowlist_proceeds(tmp_path, monkeypatch):
    """Fix 1: add_dirs inside the allowlist should be accepted."""
    import src.cli as cli

    allowed = tmp_path / "allowed"
    allowed.mkdir()
    inside = allowed / "inside"
    inside.mkdir()
    monkeypatch.setattr(cli.shutil, "which", lambda _: "agy")
    monkeypatch.setenv("ANTIGRAVITY_BRIDGE_ALLOWED_DIRS", str(allowed))
    cap = {}
    _patch_exec(monkeypatch, _FakeProc(), cap)
    out = await cli.execute_antigravity_simple_async(
        "Hi", str(allowed), add_dirs=(str(inside),)
    )
    assert out == "Answer"
    assert cap["cmd"].count("--add-dir") >= 2


async def test_add_dirs_outside_allowlist_blocked(tmp_path, monkeypatch):
    """Fix 1: add_dirs outside the allowlist must be rejected."""
    import src.cli as cli

    allowed = tmp_path / "allowed"
    allowed.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    monkeypatch.setattr(cli.shutil, "which", lambda _: "agy")
    monkeypatch.setenv("ANTIGRAVITY_BRIDGE_ALLOWED_DIRS", str(allowed))
    _patch_exec(monkeypatch, _FakeProc())
    out = await cli.execute_antigravity_simple_async(
        "Hi", str(allowed), add_dirs=(str(outside),)
    )
    assert "not in allowlist" in out.lower()


async def test_add_dirs_nonexistent_blocked(tmp_path, monkeypatch):
    """Fix 1: a nonexistent add_dirs entry must be rejected."""
    import src.cli as cli

    monkeypatch.setattr(cli.shutil, "which", lambda _: "agy")
    _patch_exec(monkeypatch, _FakeProc())
    out = await cli.execute_antigravity_simple_async(
        "Hi", str(tmp_path), add_dirs=(str(tmp_path / "nope"),)
    )
    assert "Directory does not exist" in out


async def test_health_probe_timeout_kills_proc(monkeypatch):
    """Fix 2: a timed-out health probe must kill the subprocess."""
    import src.cli as cli

    cli.reset_health_cache()
    monkeypatch.setattr(cli.shutil, "which", lambda _: "agy")
    proc = _TimeoutProc()
    monkeypatch.setattr(cli.asyncio, "create_subprocess_exec", _proc_returning(proc))
    healthy = await cli.ensure_healthy()
    assert healthy is False
    assert proc.killed is True


async def test_cancellation_kills_subprocess(monkeypatch, tmp_path):
    """Fix 3: cancelling an agy call must not orphan the subprocess."""
    import src.cli as cli

    monkeypatch.setattr(cli.shutil, "which", lambda _: "agy")
    proc = _CancelledProc()
    _patch_exec(monkeypatch, proc)
    with pytest.raises(asyncio.CancelledError):
        await cli._run_agy_async(["agy", "--print", "x"], str(tmp_path), 5)
    assert proc.killed is True


async def test_oserror_at_spawn_mapped(monkeypatch, tmp_path):
    """Fix 4: OSError from spawn must be mapped to a launch error string."""
    import src.cli as cli

    async def failing_exec(*args, **kwargs):
        raise OSError("too many open files")

    monkeypatch.setattr(cli.asyncio, "create_subprocess_exec", failing_exec)
    result = await cli._run_agy_async(["agy", "--print", "x"], str(tmp_path), 5)
    assert not result.success
    assert "Error launching Antigravity CLI" in result.output


async def test_health_lock_exists():
    """Fix 5: the health-check lock is a module-level asyncio.Lock."""
    import src.cli as cli

    assert isinstance(cli._health_lock, asyncio.Lock)


async def test_health_cached_fast_path_still_true(monkeypatch):
    """Fix 5: a cached True result short-circuits without taking the lock."""
    import src.cli as cli

    cli.reset_health_cache()
    monkeypatch.setattr(cli.shutil, "which", lambda _: "agy")
    calls = []

    async def fake_exec(*args, **kwargs):
        calls.append(args)
        return _FakeProc(0, b"agy 1.2.3\n", b"")

    monkeypatch.setattr(cli.asyncio, "create_subprocess_exec", fake_exec)
    assert await cli.ensure_healthy() is True
    first_calls = len(calls)
    assert await cli.ensure_healthy() is True
    assert len(calls) == first_calls  # still cached, no new spawn


def _proc_returning(proc):
    async def fake_exec(*args, **kwargs):
        return proc

    return fake_exec


# ---------------------------------------------------------------------------
# PTY-backed execution (agy upstream bug #318 workaround)
# ---------------------------------------------------------------------------


def test_normalize_pty_output():
    import src.cli as cli

    raw = b"\x1b[32mHello\r\nWorld\x1b[0m\r\n"
    assert cli._normalize_pty_output(raw) == "Hello\nWorld\n"


async def test_run_agy_async_dispatches_to_pty(monkeypatch, tmp_path):
    import src.cli as cli

    seen = {}

    async def fake_pty(cmd, cwd, timeout):
        seen["called"] = True
        seen["cmd"] = cmd
        return cli._ExecResult(True, "OK", "")

    monkeypatch.setattr(cli, "_run_agy_pty", fake_pty)
    res = await cli._run_agy_async(
        ["agy", "--print", "x"], str(tmp_path), 5, use_pty=True
    )
    assert seen["called"] is True
    assert res.success and res.output == "OK"


async def test_pty_happy_path_normalizes(monkeypatch, tmp_path):
    import src.cli as cli

    monkeypatch.setattr("pty.openpty", lambda: (42, 43))
    monkeypatch.setattr(cli.os, "close", lambda fd: None)
    monkeypatch.setattr(
        cli.asyncio,
        "create_subprocess_exec",
        _proc_returning(_FakeProc(0)),
    )

    async def fake_read(fd):
        return b"\x1b[1mAnswer\r\nhere\x1b[0m"

    monkeypatch.setattr(cli, "_read_fd_all", fake_read)
    res = await cli._run_agy_pty(["agy", "--print", "x"], str(tmp_path), 5)
    assert res.success
    assert res.output == "Answer\nhere"


async def test_pty_empty_output(monkeypatch, tmp_path):
    import src.cli as cli

    monkeypatch.setattr("pty.openpty", lambda: (42, 43))
    monkeypatch.setattr(cli.os, "close", lambda fd: None)
    monkeypatch.setattr(
        cli.asyncio,
        "create_subprocess_exec",
        _proc_returning(_FakeProc(0)),
    )

    async def fake_read(fd):
        return b""

    monkeypatch.setattr(cli, "_read_fd_all", fake_read)
    res = await cli._run_agy_pty(["agy", "--print", "x"], str(tmp_path), 5)
    assert res.success
    assert res.output == "No output from Antigravity CLI"


async def test_pty_timeout_kills_process_group(monkeypatch, tmp_path):
    import src.cli as cli

    monkeypatch.setattr("pty.openpty", lambda: (42, 43))
    monkeypatch.setattr(cli.os, "close", lambda fd: None)
    # returncode stays None so the process group teardown actually runs.
    monkeypatch.setattr(
        cli.asyncio,
        "create_subprocess_exec",
        _proc_returning(_FakeProc(returncode=None)),
    )
    monkeypatch.setattr(cli.os, "getpgid", lambda pid: 999)
    killed = {}
    monkeypatch.setattr(
        cli.os, "killpg", lambda pgid, sig: killed.setdefault("pgid", pgid)
    )

    async def slow_read(fd):
        await asyncio.sleep(20)
        return b""

    monkeypatch.setattr(cli, "_read_fd_all", slow_read)
    res = await cli._run_agy_pty(["agy", "--print", "x"], str(tmp_path), 1)
    assert not res.success
    assert "timed out" in res.output
    assert killed.get("pgid") == 999


async def test_pty_alloc_failure(monkeypatch, tmp_path):
    import src.cli as cli

    def boom():
        raise OSError("no pty available")

    monkeypatch.setattr("pty.openpty", boom)
    res = await cli._run_agy_pty(["agy", "--print", "x"], str(tmp_path), 5)
    assert not res.success
    assert "pseudo-TTY" in res.output


async def test_pty_spawn_failure_closes_both_fds(monkeypatch, tmp_path):
    """Regression: a spawn failure must release both PTY fds.

    The early ``return`` on spawn failure used to run only the inner ``finally``
    (closing slave_fd) and skip the outer one, leaking master_fd once per failed
    spawn. The restructured single try/finally must close both.
    """
    import src.cli as cli

    closed: list[int] = []
    monkeypatch.setattr("pty.openpty", lambda: (42, 43))
    monkeypatch.setattr(cli.os, "close", lambda fd: closed.append(fd))

    async def failing_spawn(*args, **kwargs):
        raise FileNotFoundError()

    monkeypatch.setattr(cli.asyncio, "create_subprocess_exec", failing_spawn)
    res = await cli._run_agy_pty(["agy", "--print", "x"], str(tmp_path), 5)
    assert not res.success
    assert "Antigravity CLI not found" in res.output
    assert 42 in closed  # master_fd — the previously leaked descriptor
    assert 43 in closed  # slave_fd


async def test_force_tty_true_routes_through_pty(monkeypatch, tmp_path):
    """The print path honours ANTIGRAVITY_BRIDGE_FORCE_TTY=true (the default)."""
    import src.cli as cli

    monkeypatch.setattr(cli.shutil, "which", lambda _: "agy")
    monkeypatch.setenv("ANTIGRAVITY_BRIDGE_FORCE_TTY", "true")
    monkeypatch.setenv("ANTIGRAVITY_BRIDGE_HEALTH_CHECK", "false")
    seen = {}

    async def fake_retry(cmd, cwd, timeout, settings, rid, *, use_pty=False):
        seen["use_pty"] = use_pty
        return cli._ExecResult(True, "OK", "")

    monkeypatch.setattr(cli, "_run_with_retry", fake_retry)
    out = await cli.execute_antigravity_simple_async("Hi", str(tmp_path))
    assert out == "OK"
    assert seen["use_pty"] is True


async def test_models_ignores_force_tty(monkeypatch, tmp_path):
    """``agy models`` runs headless even when FORCE_TTY is true."""
    import src.cli as cli

    monkeypatch.setattr(cli.shutil, "which", lambda _: "agy")
    monkeypatch.setenv("ANTIGRAVITY_BRIDGE_FORCE_TTY", "true")
    monkeypatch.setenv("ANTIGRAVITY_BRIDGE_HEALTH_CHECK", "false")
    seen = {}

    async def fake_retry(cmd, cwd, timeout, settings, rid, *, use_pty=False):
        seen["use_pty"] = use_pty
        return cli._ExecResult(True, "Gemini 3.5 Flash", "")

    monkeypatch.setattr(cli, "_run_with_retry", fake_retry)
    await cli.execute_antigravity_models_async()
    assert seen["use_pty"] is False


# ---------------------------------------------------------------------------
# PTY execution: exit-code mapping, auth detection, cancellation, teardown
# ---------------------------------------------------------------------------


def _pty_harness(monkeypatch, proc, read_payload):
    """Wire up the PTY path with fake fds + a canned read, return nothing."""
    import src.cli as cli

    monkeypatch.setattr("pty.openpty", lambda: (42, 43))
    monkeypatch.setattr(cli.os, "close", lambda fd: None)
    monkeypatch.setattr(cli.asyncio, "create_subprocess_exec", _proc_returning(proc))

    async def fake_read(fd):
        return read_payload

    monkeypatch.setattr(cli, "_read_fd_all", fake_read)


async def test_pty_nonzero_exit_maps_error(monkeypatch, tmp_path):
    import src.cli as cli

    _pty_harness(monkeypatch, _FakeProc(1), b"something went wrong")
    res = await cli._run_agy_pty(["agy", "--print", "x"], str(tmp_path), 5)
    assert not res.success
    assert "Antigravity CLI Error" in res.output
    assert "something went wrong" in res.output


async def test_pty_auth_error_detected(monkeypatch, tmp_path):
    import src.cli as cli

    _pty_harness(monkeypatch, _FakeProc(1), b"Error: authentication required")
    res = await cli._run_agy_pty(["agy", "--print", "x"], str(tmp_path), 5)
    assert not res.success
    assert "Authentication required" in res.output


async def test_pty_cancellation_kills_process_group(monkeypatch, tmp_path):
    import src.cli as cli

    monkeypatch.setattr("pty.openpty", lambda: (42, 43))
    monkeypatch.setattr(cli.os, "close", lambda fd: None)
    monkeypatch.setattr(cli.os, "getpgid", lambda pid: 999)
    killed = {}
    monkeypatch.setattr(
        cli.os, "killpg", lambda pgid, sig: killed.setdefault("pgid", pgid)
    )
    monkeypatch.setattr(
        cli.asyncio,
        "create_subprocess_exec",
        _proc_returning(_FakeProc(returncode=None)),
    )

    async def read_then_cancel(fd):
        raise asyncio.CancelledError()

    monkeypatch.setattr(cli, "_read_fd_all", read_then_cancel)
    with pytest.raises(asyncio.CancelledError):
        await cli._run_agy_pty(["agy", "--print", "x"], str(tmp_path), 5)
    assert killed.get("pgid") == 999


def test_terminate_process_group_permission_fallback(monkeypatch):
    """If killpg is denied, fall back to proc.kill()."""
    import src.cli as cli

    proc = _FakeProc(returncode=None)
    monkeypatch.setattr(cli.os, "getpgid", lambda pid: 999)
    monkeypatch.setattr(
        cli.os,
        "killpg",
        lambda pgid, sig: (_ for _ in ()).throw(PermissionError()),
    )
    cli._terminate_process_group(proc)
    assert proc.killed is True


def test_terminate_process_group_noop_on_finished():
    """A process that already exited is left alone."""
    import src.cli as cli

    proc = _FakeProc(returncode=0)
    cli._terminate_process_group(proc)
    assert proc.killed is False


def test_normalize_pty_output_strips_osc_sequences():
    import src.cli as cli

    # OSC title-set sequence + trailing CR should be removed.
    raw = b"\x1b]0;title\x07Hello\r\n"
    assert cli._normalize_pty_output(raw) == "Hello\n"
