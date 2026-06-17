import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(autouse=True)
def clear_env_vars(monkeypatch):
    for v in [
        "ANTIGRAVITY_BRIDGE_TIMEOUT",
        "ANTIGRAVITY_BRIDGE_SKIP_PERMISSIONS",
        "ANTIGRAVITY_BRIDGE_SANDBOX",
        "ANTIGRAVITY_BRIDGE_MODEL",
        "ANTIGRAVITY_BRIDGE_MAX_QUERY_LENGTH",
        "ANTIGRAVITY_BRIDGE_ALLOWED_DIRS",
    ]:
        monkeypatch.delenv(v, raising=False)


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
        return "response"

    monkeypatch.setattr(tools.cli, "execute_antigravity_simple_async", fake)
    result = await tools.agy_consult("Hello", str(tmp_path))
    assert result == "response"
    assert captured["query"] == "Hello"
    assert captured["directory"] == str(tmp_path)


async def test_agy_consult_forwards_model(tmp_path, monkeypatch):
    import src.tools as tools

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
        return "ok"

    monkeypatch.setattr(tools.cli, "execute_antigravity_simple_async", fake)
    await tools.agy_consult("Hi", str(tmp_path), model="gemini-3.5-flash")
    assert captured["model"] == "gemini-3.5-flash"


async def test_agy_consult_rejects_oversized_query(tmp_path, monkeypatch):
    import src.tools as tools

    monkeypatch.setenv("ANTIGRAVITY_BRIDGE_MAX_QUERY_LENGTH", "10")
    result = await tools.agy_consult("x" * 50, str(tmp_path))
    assert "exceeds max length" in result or "too long" in result.lower()


async def test_agy_consult_with_files_requires_files(tmp_path, monkeypatch):
    import src.tools as tools

    result = await tools.agy_consult_with_files("Hello", str(tmp_path), files=None)
    assert "files parameter is required" in result


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
        return "review"

    monkeypatch.setattr(tools.cli, "execute_antigravity_with_files_async", fake)
    result = await tools.agy_consult_with_files(
        "Review", str(tmp_path), files=["a.py"], mode="at_command"
    )
    assert "review" in result
    assert captured["mode"] == "at_command"
    assert captured["files_list"] == ["a.py"]


async def test_agy_web_search_prepends_instruction(tmp_path, monkeypatch):
    import src.tools as tools

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
        return "search result"

    monkeypatch.setattr(tools.cli, "execute_antigravity_simple_async", fake)
    result = await tools.agy_web_search(
        "Python version",
        str(tmp_path),
        model="gemini-3.5-flash",
        add_dirs=["/tmp/extra"],
        conversation_id="conv-123",
        continue_last=True,
    )
    assert "search result" in result
    assert (
        "Please use web search to find current information about" in captured["query"]
    )
    assert captured["model"] == "gemini-3.5-flash"
    assert captured["add_dirs"] == ("/tmp/extra",)
    assert captured["conversation_id"] == "conv-123"
    assert captured["continue_last"] is True


def test_mcp_server_name():
    import src.tools as tools

    assert tools.mcp.name == "antigravity-bridge"


def test_mcp_server_advertises_app_version():
    """The handshake must report the app version, not the mcp SDK version."""
    import src
    import src.tools as tools

    advertised = tools.mcp._mcp_server.version
    assert advertised == src.__version__
    # Must NOT be the installed mcp SDK version leak.
    from importlib.metadata import version as pkg_version

    assert advertised != pkg_version("mcp")


def test_mcp_handshake_advertises_app_version():
    """Real initialize handshake returns the app version in serverInfo.version."""
    import json
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


async def test_agy_list_models_delegates(tmp_path, monkeypatch):
    import src.tools as tools

    async def fake():
        return "Gemini 3.5 Flash\nClaude Sonnet 4.6"

    monkeypatch.setattr(tools.cli, "execute_antigravity_models_async", fake)
    result = await tools.agy_list_models()
    assert "Gemini" in result


def test_main_sets_up_logging_and_signals(monkeypatch):
    import signal as _signal
    from types import SimpleNamespace

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
    import pytest

    import src.tools as tools

    monkeypatch.setattr(tools.observability, "setup_logging", lambda *a, **k: None)

    def bad():
        raise tools.config.ConfigError("bad timeout")

    monkeypatch.setattr(tools.config, "validate_config", bad)
    with pytest.raises(SystemExit) as exc_info:
        tools.main()
    assert exc_info.value.code == 1
