import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class _FakeCtx:
    """Minimal stand-in for mcp.server.fastmcp.Context — records log calls."""

    def __init__(self) -> None:
        self.events: list[tuple[str, str]] = []

    async def info(self, message: str, **extra: object) -> None:
        self.events.append(("info", message))

    async def warning(self, message: str, **extra: object) -> None:
        self.events.append(("warning", message))

    async def error(self, message: str, **extra: object) -> None:
        self.events.append(("error", message))

    async def debug(self, message: str, **extra: object) -> None:
        self.events.append(("debug", message))


@pytest.fixture(autouse=True)
def clear_env_vars(monkeypatch):
    for v in [
        "ANTIGRAVITY_BRIDGE_TIMEOUT",
        "ANTIGRAVITY_BRIDGE_SKIP_PERMISSIONS",
        "ANTIGRAVITY_BRIDGE_SANDBOX",
        "ANTIGRAVITY_BRIDGE_MODEL",
        "ANTIGRAVITY_BRIDGE_MAX_QUERY_LENGTH",
        "ANTIGRAVITY_BRIDGE_ALLOWED_DIRS",
        "ANTIGRAVITY_BRIDGE_FORCE_TTY",
    ]:
        monkeypatch.delenv(v, raising=False)
    # The model-name cache is module-global; reset it between tests.
    import src.tools as tools

    tools._models_cache = None


def _ok(output: str = "response", model: str = "", warnings=None, duration_ms=1.0):
    from src.cli import AgyOutcome

    return AgyOutcome(
        success=True,
        output=output,
        model=model,
        warnings=warnings or [],
        duration_ms=duration_ms,
    )


def _err(output: str = "boom", model: str = ""):
    from src.cli import AgyOutcome

    return AgyOutcome(success=False, output=output, model=model)


# ---------------------------------------------------------------------------
# agy_consult
# ---------------------------------------------------------------------------


async def test_agy_consult_is_async_and_delegates(tmp_path, monkeypatch):
    import inspect

    import src.tools as tools

    assert inspect.iscoroutinefunction(tools.agy_consult)

    captured = {}

    async def fake(
        query,
        directory,
        timeout_seconds=None,
        model="",
        add_dirs=(),
        conversation_id="",
        continue_last=False,
    ):
        captured.update(query=query, directory=directory, model=model)
        return _ok("response", model=model)

    monkeypatch.setattr(tools.cli, "execute_antigravity_simple_outcome_async", fake)
    result = await tools.agy_consult("Hello", str(tmp_path), None)
    assert isinstance(result, tools.AgyResult)
    assert result.success is True
    assert result.output == "response"
    assert result.model == ""
    assert captured["query"] == "Hello"
    assert captured["directory"] == str(tmp_path)


async def test_agy_consult_forwards_model(tmp_path, monkeypatch):
    import src.tools as tools

    tools._models_cache = ["gemini-3.5-flash"]
    captured = {}

    async def fake(
        query,
        directory,
        timeout_seconds=None,
        model="",
        add_dirs=(),
        conversation_id="",
        continue_last=False,
    ):
        captured["model"] = model
        return _ok("ok", model=model)

    monkeypatch.setattr(tools.cli, "execute_antigravity_simple_outcome_async", fake)
    result = await tools.agy_consult(
        "Hi", str(tmp_path), None, model="gemini-3.5-flash"
    )
    assert captured["model"] == "gemini-3.5-flash"
    assert result.model == "gemini-3.5-flash"


async def test_agy_consult_rejects_unsupported_model(tmp_path, monkeypatch):
    import src.tools as tools

    tools._models_cache = ["gemini-3.5-flash"]
    with pytest.raises(tools.ToolError) as exc_info:
        await tools.agy_consult("Hi", str(tmp_path), None, model="invalid-model")
    assert "not supported" in str(exc_info.value)


async def test_validate_model_accepts_supported(tmp_path, monkeypatch):
    import src.tools as tools

    tools._models_cache = ["Model A", "Claude Opus 4.6 (Thinking)"]
    # Must not raise.
    await tools._validate_model("Claude Opus 4.6 (Thinking)")


async def test_validate_model_skips_empty_model(tmp_path, monkeypatch):
    import src.tools as tools

    # Empty model short-circuits without touching the cache.
    tools._models_cache = None
    await tools._validate_model("")


async def test_validate_model_skips_when_models_unavailable(tmp_path, monkeypatch):
    import src.tools as tools

    # Empty list (agy unavailable) → validation degrades gracefully.
    tools._models_cache = []
    await tools._validate_model("anything")


async def test_agy_consult_rejects_oversized_query(tmp_path, monkeypatch):
    import src.tools as tools

    monkeypatch.setenv("ANTIGRAVITY_BRIDGE_MAX_QUERY_LENGTH", "10")
    with pytest.raises(tools.ToolError):
        await tools.agy_consult("x" * 50, str(tmp_path), None)


async def test_agy_consult_raises_on_failure(tmp_path, monkeypatch):
    import src.tools as tools

    async def fake(*a, **k):
        return _err("Antigravity CLI Error: connection reset")

    monkeypatch.setattr(tools.cli, "execute_antigravity_simple_outcome_async", fake)
    with pytest.raises(tools.ToolError):
        await tools.agy_consult("Hi", str(tmp_path), None)


async def test_agy_consult_logs_to_context(tmp_path, monkeypatch):
    import src.tools as tools

    async def fake(*a, **k):
        return _ok("response")

    monkeypatch.setattr(tools.cli, "execute_antigravity_simple_outcome_async", fake)
    ctx = _FakeCtx()
    await tools.agy_consult("Hi", str(tmp_path), ctx)
    levels = [lvl for lvl, _ in ctx.events]
    assert "info" in levels  # start + done


# ---------------------------------------------------------------------------
# agy_consult_with_files
# ---------------------------------------------------------------------------


async def test_agy_consult_with_files_requires_files(tmp_path, monkeypatch):
    import src.tools as tools

    with pytest.raises(tools.ToolError):
        await tools.agy_consult_with_files("Hello", str(tmp_path), None, None)


async def test_agy_consult_with_files_delegates(tmp_path, monkeypatch):
    import src.tools as tools

    captured = {}

    async def fake(
        query,
        directory,
        files_list=None,
        timeout_seconds=None,
        mode="inline",
        model="",
        add_dirs=(),
        conversation_id="",
        continue_last=False,
    ):
        captured.update(mode=mode, files_list=files_list)
        return _ok("review")

    monkeypatch.setattr(tools.cli, "execute_antigravity_with_files_outcome_async", fake)
    result = await tools.agy_consult_with_files(
        "Review", str(tmp_path), ["a.py"], None, mode="at_command"
    )
    assert isinstance(result, tools.AgyResult)
    assert result.output == "review"
    assert captured["mode"] == "at_command"
    assert captured["files_list"] == ["a.py"]


async def test_agy_consult_with_files_propagates_warnings(tmp_path, monkeypatch):
    import src.tools as tools

    async def fake(*a, **k):
        return _ok("review", warnings=["Skipped missing file: x.txt"])

    monkeypatch.setattr(tools.cli, "execute_antigravity_with_files_outcome_async", fake)
    result = await tools.agy_consult_with_files(
        "Review", str(tmp_path), ["x.txt"], None
    )
    assert result.warnings == ["Skipped missing file: x.txt"]


# ---------------------------------------------------------------------------
# agy_web_search
# ---------------------------------------------------------------------------


async def test_agy_web_search_prepends_instruction(tmp_path, monkeypatch):
    import src.tools as tools

    tools._models_cache = ["gemini-3.5-flash"]
    captured = {}

    async def fake(
        query,
        directory,
        timeout_seconds=None,
        model="",
        add_dirs=(),
        conversation_id="",
        continue_last=False,
    ):
        captured.update(
            query=query,
            model=model,
            add_dirs=add_dirs,
            conversation_id=conversation_id,
            continue_last=continue_last,
        )
        return _ok("search result", model=model)

    monkeypatch.setattr(tools.cli, "execute_antigravity_simple_outcome_async", fake)
    result = await tools.agy_web_search(
        "Python version",
        None,
        str(tmp_path),
        model="gemini-3.5-flash",
        add_dirs=["/tmp/extra"],
        conversation_id="conv-123",
        continue_last=True,
    )
    assert result.output == "search result"
    assert (
        "Please use web search to find current information about" in captured["query"]
    )
    assert captured["model"] == "gemini-3.5-flash"
    assert captured["add_dirs"] == ("/tmp/extra",)
    assert captured["conversation_id"] == "conv-123"
    assert captured["continue_last"] is True


# ---------------------------------------------------------------------------
# agy_list_models
# ---------------------------------------------------------------------------


async def test_agy_list_models_delegates(tmp_path, monkeypatch):
    import src.tools as tools

    async def fake():
        return _ok("Gemini 3.5 Flash\nClaude Sonnet 4.6")

    monkeypatch.setattr(tools.cli, "execute_antigravity_models_outcome_async", fake)
    result = await tools.agy_list_models(None)
    assert isinstance(result, tools.AgyResult)
    assert "Gemini" in result.output
    # Listing also primes the completion cache as a side effect.
    assert tools._models_cache is not None
    assert "Gemini 3.5 Flash" in tools._models_cache


# ---------------------------------------------------------------------------
# tool annotations / titles / instructions
# ---------------------------------------------------------------------------


def test_tools_carry_annotations_and_titles():
    import src.tools as tools

    seen = tools.mcp._tool_manager.list_tools()
    by_name = {t.name: t for t in seen}
    consult = by_name["agy_consult"]
    assert consult.title == "Consult Antigravity (agy)"
    assert consult.annotations is not None
    assert consult.annotations.readOnlyHint is False
    assert consult.annotations.openWorldHint is True
    models = by_name["agy_list_models"]
    assert models.annotations.readOnlyHint is True


def test_tool_schema_excludes_ctx_and_forbids_extras():
    """Regression: ``ctx`` must be injected, not exposed as a required arg, and
    the input schema must forbid unknown parameters."""
    import src.tools as tools

    for name in (
        "agy_consult",
        "agy_consult_with_files",
        "agy_web_search",
        "agy_list_models",
    ):
        tool = tools.mcp._tool_manager._tools[name]
        schema = tool.parameters
        # ctx is never a user-facing argument
        assert "ctx" not in schema.get("properties", {}), name
        assert "ctx" not in schema.get("required", []), name
        # The tool must be wired to receive the injected context.
        assert tool.context_kwarg == "ctx", name
        # Unknown parameters must be rejected (advertised to clients).
        assert schema.get("additionalProperties") is False, name


async def test_agy_consult_rejects_unknown_argument():
    """Passing a parameter the tool does not declare must raise a ToolError."""
    import src.tools as tools

    tool = tools.mcp._tool_manager._tools["agy_consult"]
    with pytest.raises(tools.ToolError) as exc_info:
        await tool.run(
            {"query": "hi", "directory": "/tmp", "bogus_opt": 123}, context=None
        )
    assert "bogus_opt" in str(exc_info.value)


async def test_agy_consult_run_injects_context(tmp_path, monkeypatch):
    """Regression: FastMCP must auto-inject ``ctx`` on the ``tool.run`` path.

    With postponed annotations (``from __future__ import annotations``) FastMCP
    cannot detect ``ctx`` as the injected context kwarg, exposes it as a
    *required* user argument, and every ``tool.run`` fails with
    ``ctx - Field required``. Driving the tool through its real ``run`` entry
    point with a context object confirms the context is both injected and used.
    """
    import src.tools as tools

    async def fake(*a, **k):
        return _ok("response")

    monkeypatch.setattr(tools.cli, "execute_antigravity_simple_outcome_async", fake)
    tool = tools.mcp._tool_manager._tools["agy_consult"]
    ctx = _FakeCtx()
    # If ctx were not auto-injected, this call raises instead of returning.
    await tool.run({"query": "Hi", "directory": str(tmp_path)}, context=ctx)
    assert any(lvl == "info" for lvl, _ in ctx.events)


async def test_agy_consult_with_files_rejects_bad_mode(tmp_path, monkeypatch):
    """An unsupported ``mode`` must fail fast with a ToolError, before any CLI call."""
    import src.tools as tools

    # Ensure no subprocess can run if validation somehow misses.
    async def boom(*a, **k):
        raise AssertionError("executor should not run for a bad mode")

    monkeypatch.setattr(tools.cli, "execute_antigravity_with_files_outcome_async", boom)
    with pytest.raises(tools.ToolError) as exc_info:
        await tools.agy_consult_with_files(
            "Review", str(tmp_path), ["x.py"], None, mode="weird"
        )
    assert "Unsupported files mode" in str(exc_info.value)


def test_server_has_instructions():
    import src.tools as tools

    assert tools.mcp.instructions and "agy_consult" in tools.mcp.instructions


# ---------------------------------------------------------------------------
# resource
# ---------------------------------------------------------------------------


def test_settings_resource_includes_version():
    import src
    import src.tools as tools

    payload = json.loads(tools.settings_resource())
    assert payload["version"] == src.__version__
    assert "default_timeout" in payload
    assert "force_tty" in payload
    # No secret fields exist, but ensure no placeholder key leaks.
    assert "api_key" not in payload


def test_settings_resource_complete_and_humanized():
    """The resource exposes every Settings field plus human-readable companions."""
    import src.tools as tools

    payload = json.loads(tools.settings_resource())
    # The two previously-missing truncation-chunk settings are now present.
    assert "inline_chunk_head_bytes" in payload
    assert "inline_chunk_tail_bytes" in payload
    # Dimensional settings carry a ``*_human`` companion.
    assert payload["max_inline_file_bytes_human"] == "512.0 KB"
    assert payload["max_inline_total_bytes_human"] == "1.0 MB"
    assert payload["inline_chunk_head_bytes_human"] == "64.0 KB"
    assert payload["default_timeout_human"] == "600 s"
    assert payload["max_query_length_human"] == "100000 chars"
    # Scalar values remain machine-parseable (backward compatible).
    assert payload["max_inline_file_bytes"] == 524288
    assert isinstance(payload["default_timeout"], int)


# ---------------------------------------------------------------------------
# prompts
# ---------------------------------------------------------------------------


def test_investigate_project_prompt():
    import src.tools as tools

    text = tools.investigate_project("/repo", exclude="web/")
    assert "/repo" in text
    assert "web/" in text


def test_code_review_prompt():
    import src.tools as tools

    text = tools.code_review("/repo", focus="security")
    assert "/repo" in text
    assert "security" in text


def test_consult_prompt_includes_model():
    import src.tools as tools

    assert tools.consult("hello", model="X") == "[model: X] hello"
    assert tools.consult("hello") == "hello"


# ---------------------------------------------------------------------------
# completion
# ---------------------------------------------------------------------------


async def test_fetch_model_names_caches(tmp_path, monkeypatch):
    import src.tools as tools

    calls = []

    async def fake_models():
        calls.append(1)
        return "Model A\nModel B"

    monkeypatch.setattr(tools.cli, "execute_antigravity_models_async", fake_models)
    first = await tools._fetch_model_names()
    second = await tools._fetch_model_names()
    assert first == ["Model A", "Model B"]
    assert second == first
    assert len(calls) == 1  # cached after first call


async def test_fetch_model_names_rejects_error_output(tmp_path, monkeypatch):
    import src.tools as tools

    async def fake_models():
        return "Error: Antigravity CLI not found. Install with: ..."

    monkeypatch.setattr(tools.cli, "execute_antigravity_models_async", fake_models)
    assert await tools._fetch_model_names() == []


async def test_completion_suggests_models_for_model_arg(tmp_path, monkeypatch):
    import src.tools as tools

    async def fake_models():
        return "Model A\nModel B"

    monkeypatch.setattr(tools.cli, "execute_antigravity_models_async", fake_models)
    res = await tools._complete_arguments(None, SimpleNamespace(name="model"), None)
    assert res is not None
    assert "Model A" in res.values


async def test_completion_ignores_other_args(tmp_path, monkeypatch):
    import src.tools as tools

    res = await tools._complete_arguments(None, SimpleNamespace(name="directory"), None)
    assert res is None


# ---------------------------------------------------------------------------
# failure paths (every tool raises ToolError on an unsuccessful outcome)
# ---------------------------------------------------------------------------


async def test_agy_consult_with_files_raises_on_failure(tmp_path, monkeypatch):
    import src.tools as tools

    async def fake(*a, **k):
        return _err("Antigravity CLI Error: timed out")

    monkeypatch.setattr(tools.cli, "execute_antigravity_with_files_outcome_async", fake)
    with pytest.raises(tools.ToolError):
        await tools.agy_consult_with_files("Review", str(tmp_path), ["x.py"], None)


async def test_agy_web_search_raises_on_failure(tmp_path, monkeypatch):
    import src.tools as tools

    tools._models_cache = []  # skip model validation

    async def fake(*a, **k):
        return _err("Antigravity CLI Error: auth")

    monkeypatch.setattr(tools.cli, "execute_antigravity_simple_outcome_async", fake)
    with pytest.raises(tools.ToolError):
        await tools.agy_web_search("anything", None, str(tmp_path))


async def test_agy_list_models_raises_on_failure(monkeypatch):
    import src.tools as tools

    async def fake():
        return _err("Antigravity CLI not found")

    monkeypatch.setattr(tools.cli, "execute_antigravity_models_outcome_async", fake)
    with pytest.raises(tools.ToolError):
        await tools.agy_list_models(None)


# ---------------------------------------------------------------------------
# helper edge cases
# ---------------------------------------------------------------------------


async def test_fetch_model_names_swallows_exception(monkeypatch):
    import src.tools as tools

    async def boom():
        raise RuntimeError("agy exploded")

    monkeypatch.setattr(tools.cli, "execute_antigravity_models_async", boom)
    assert await tools._fetch_model_names() == []


async def test_notify_skips_missing_handler():
    """A ctx object without the requested level method must not crash."""
    import src.tools as tools

    class _Empty:
        pass

    await tools._notify(_Empty(), "info", "hello")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# server metadata + entry point
# ---------------------------------------------------------------------------


def test_mcp_server_name():
    import src.tools as tools

    assert tools.mcp.name == "antigravity-bridge"


def test_mcp_server_advertises_app_version():
    """The handshake must report the app version, not the mcp SDK version."""
    import src
    import src.tools as tools

    advertised = tools.mcp._mcp_server.version
    assert advertised == src.__version__
    from importlib.metadata import version as pkg_version

    assert advertised != pkg_version("mcp")


def test_mcp_handshake_advertises_app_version():
    """Real initialize handshake returns the app version in serverInfo.version."""
    import subprocess

    import src

    repo_root = Path(__file__).resolve().parents[1]
    req = (
        '{"jsonrpc":"2.0","id":1,"method":"initialize",'
        '"params":{"protocolVersion":"2024-11-05","capabilities":{},'
        '"clientInfo":{"name":"t","version":"1"}}}\n'
    )
    proc = subprocess.run(
        ["python3", "-m", "src"],
        input=req,
        text=True,
        capture_output=True,
        timeout=8,
        cwd=str(repo_root),
    )
    assert proc.returncode == 0, f"server exited {proc.returncode}: {proc.stderr}"
    line = proc.stdout.splitlines()[0]
    resp = json.loads(line)
    assert resp["result"]["serverInfo"]["version"] == src.__version__


def test_main_function_exists():
    import src.tools as tools

    assert callable(tools.main)


def test_main_sets_up_logging_and_signals(monkeypatch):
    import signal as _signal

    import src.tools as tools

    setup_calls = {}

    def fake_setup(level, fmt):
        setup_calls["args"] = (level, fmt)

    monkeypatch.setattr(tools.observability, "setup_logging", fake_setup)
    monkeypatch.setattr(tools.config, "validate_config", lambda: None)
    monkeypatch.setattr(tools, "mcp", SimpleNamespace(run=lambda: None))

    registered = []
    monkeypatch.setattr(
        tools.signal, "signal", lambda sig, handler: registered.append(sig)
    )

    tools.main()
    assert "args" in setup_calls
    assert _signal.SIGTERM in registered
    assert _signal.SIGINT in registered


def test_main_config_error_exits(monkeypatch):
    import src.tools as tools

    monkeypatch.setattr(tools.observability, "setup_logging", lambda *a, **k: None)

    def bad():
        raise tools.config.ConfigError("bad timeout")

    monkeypatch.setattr(tools.config, "validate_config", bad)
    with pytest.raises(SystemExit) as exc_info:
        tools.main()
    assert exc_info.value.code == 1


def test_main_run_swallows_keyboard_interrupt(monkeypatch):
    """A KeyboardInterrupt from mcp.run() is caught and logged, not propagated."""
    import src.tools as tools

    monkeypatch.setattr(tools.observability, "setup_logging", lambda *a, **k: None)
    monkeypatch.setattr(tools.config, "validate_config", lambda: None)

    def raise_kbi():
        raise KeyboardInterrupt

    monkeypatch.setattr(tools, "mcp", SimpleNamespace(run=raise_kbi))
    monkeypatch.setattr(tools.signal, "signal", lambda sig, handler: None)
    tools.main()  # must not raise


def test_main_shutdown_handler_exits_cleanly(monkeypatch):
    """The registered signal handler exits with code 0 when invoked."""
    import src.tools as tools

    captured = {}

    def fake_signal(sig, handler):
        captured[sig] = handler

    monkeypatch.setattr(tools.observability, "setup_logging", lambda *a, **k: None)
    monkeypatch.setattr(tools.config, "validate_config", lambda: None)
    monkeypatch.setattr(tools, "mcp", SimpleNamespace(run=lambda: None))
    monkeypatch.setattr(tools.signal, "signal", fake_signal)

    tools.main()
    with pytest.raises(SystemExit) as exc_info:
        captured[tools.signal.SIGTERM](15, None)
    assert exc_info.value.code == 0
