import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(autouse=True)
def clear_env_vars(monkeypatch):
    monkeypatch.delenv("ANTIGRAVITY_BRIDGE_TIMEOUT", raising=False)
    monkeypatch.delenv("ANTIGRAVITY_BRIDGE_SKIP_PERMISSIONS", raising=False)
    monkeypatch.delenv("ANTIGRAVITY_BRIDGE_SANDBOX", raising=False)


def test_agy_consult_delegates(tmp_path, monkeypatch):
    import src.tools as tools
    monkeypatch.setattr("src.tools.cli.shutil.which", lambda _: "agy")

    def fake_run(cmd, **kwargs):
        return SimpleNamespace(returncode=0, stdout="response", stderr="")

    monkeypatch.setattr("src.tools.cli.subprocess.run", fake_run)
    result = tools.agy_consult("Hello", str(tmp_path))
    assert result == "response"


def test_agy_consult_with_files_delegates(tmp_path, monkeypatch):
    import src.tools as tools
    monkeypatch.setattr("src.tools.cli.shutil.which", lambda _: "agy")
    f = tmp_path / "f.txt"
    f.write_text("data", encoding="utf-8")

    def fake_run(cmd, **kwargs):
        return SimpleNamespace(returncode=0, stdout="review", stderr="")

    monkeypatch.setattr("src.tools.cli.subprocess.run", fake_run)
    result = tools.agy_consult_with_files("Review", str(tmp_path), files=["f.txt"])
    assert "review" in result


def test_agy_consult_with_files_requires_files(tmp_path):
    import src.tools as tools
    result = tools.agy_consult_with_files("Hello", str(tmp_path), files=None)
    assert "files parameter is required" in result


def test_agy_web_search_prepends_instruction(tmp_path, monkeypatch):
    import src.tools as tools
    monkeypatch.setattr("src.tools.cli.shutil.which", lambda _: "agy")

    captured_query = []

    def fake_execute(query, directory, timeout_seconds):
        captured_query.append(query)
        return "search result"

    monkeypatch.setattr("src.tools.cli.execute_antigravity_simple", fake_execute)
    result = tools.agy_web_search("Python version", str(tmp_path))
    assert "search result" in result
    assert "Please use web search to find current information about" in captured_query[0]


def test_mcp_server_name():
    import src.tools as tools
    assert tools.mcp.name == "antigravity-bridge"


def test_main_function_exists():
    import src.tools as tools
    assert callable(tools.main)
