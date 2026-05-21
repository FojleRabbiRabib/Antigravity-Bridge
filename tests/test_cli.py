import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(autouse=True)
def clear_env_vars(monkeypatch):
    monkeypatch.delenv("ANTIGRAVITY_BRIDGE_TIMEOUT", raising=False)
    monkeypatch.delenv("ANTIGRAVITY_BRIDGE_DEFAULT_TIMEOUT", raising=False)
    monkeypatch.delenv("ANTIGRAVITY_BRIDGE_SKIP_PERMISSIONS", raising=False)
    monkeypatch.delenv("ANTIGRAVITY_BRIDGE_SANDBOX", raising=False)


def _reload(mod, monkeypatch):
    import importlib
    return importlib.reload(mod)


def test_simple_cli_not_found(tmp_path, monkeypatch):
    import src.cli as cli
    monkeypatch.setattr("src.cli.shutil.which", lambda _: None)
    result = cli.execute_antigravity_simple("Hello", str(tmp_path))
    assert "Antigravity CLI not found" in result
    assert "antigravity.google" in result


def test_simple_invalid_directory(monkeypatch):
    import src.cli as cli
    monkeypatch.setattr("src.cli.shutil.which", lambda _: "agy")
    result = cli.execute_antigravity_simple("Hello", "non-existent-path")
    assert "Directory does not exist" in result


def test_simple_success(tmp_path, monkeypatch):
    import src.cli as cli
    _reload(cli, monkeypatch)
    monkeypatch.setattr("src.cli.shutil.which", lambda _: "agy")

    def fake_run(cmd, cwd, capture_output, text, timeout):
        assert "agy" in cmd
        assert "--print" in cmd
        assert "Hello" in cmd
        assert cwd == str(tmp_path)
        return SimpleNamespace(returncode=0, stdout="Answer\n", stderr="")

    monkeypatch.setattr("src.cli.subprocess.run", fake_run)
    result = cli.execute_antigravity_simple("Hello", str(tmp_path))
    assert result == "Answer"


def test_simple_adds_skip_permissions(tmp_path, monkeypatch):
    import src.cli as cli
    monkeypatch.setenv("ANTIGRAVITY_BRIDGE_SKIP_PERMISSIONS", "true")
    _reload(cli, monkeypatch)
    monkeypatch.setattr("src.cli.shutil.which", lambda _: "agy")

    actual_cmd = []

    def fake_run(cmd, **kwargs):
        actual_cmd.append(cmd)
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr("src.cli.subprocess.run", fake_run)
    cli.execute_antigravity_simple("Hello", str(tmp_path))
    assert "--dangerously-skip-permissions" in actual_cmd[0]


def test_simple_omits_skip_permissions_when_disabled(tmp_path, monkeypatch):
    import src.config as cfg
    import src.cli as cli
    monkeypatch.setenv("ANTIGRAVITY_BRIDGE_SKIP_PERMISSIONS", "false")
    _reload(cfg, monkeypatch)
    _reload(cli, monkeypatch)
    monkeypatch.setattr("src.cli.shutil.which", lambda _: "agy")

    actual_cmd = []

    def fake_run(cmd, **kwargs):
        actual_cmd.append(cmd)
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr("src.cli.subprocess.run", fake_run)
    cli.execute_antigravity_simple("Hello", str(tmp_path))
    assert "--dangerously-skip-permissions" not in actual_cmd[0]


def test_simple_adds_sandbox_when_enabled(tmp_path, monkeypatch):
    import src.config as cfg
    import src.cli as cli
    monkeypatch.setenv("ANTIGRAVITY_BRIDGE_SANDBOX", "true")
    _reload(cfg, monkeypatch)
    _reload(cli, monkeypatch)
    monkeypatch.setattr("src.cli.shutil.which", lambda _: "agy")

    actual_cmd = []

    def fake_run(cmd, **kwargs):
        actual_cmd.append(cmd)
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr("src.cli.subprocess.run", fake_run)
    cli.execute_antigravity_simple("Hello", str(tmp_path))
    assert "--sandbox" in actual_cmd[0]


def test_simple_timeout_override(tmp_path, monkeypatch):
    import src.cli as cli
    _reload(cli, monkeypatch)
    monkeypatch.setattr("src.cli.shutil.which", lambda _: "agy")

    def fake_run(cmd, cwd, capture_output, text, timeout):
        assert timeout == 5
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr("src.cli.subprocess.run", fake_run)
    result = cli.execute_antigravity_simple("Hello", str(tmp_path), timeout_seconds=5)
    assert result == "ok"


def test_simple_auth_error(tmp_path, monkeypatch):
    import src.cli as cli
    _reload(cli, monkeypatch)
    monkeypatch.setattr("src.cli.shutil.which", lambda _: "agy")

    def fake_run(cmd, **kwargs):
        return SimpleNamespace(returncode=1, stdout="", stderr="Authentication required")

    monkeypatch.setattr("src.cli.subprocess.run", fake_run)
    result = cli.execute_antigravity_simple("Hello", str(tmp_path))
    assert "Authentication required" in result


def test_simple_generic_error(tmp_path, monkeypatch):
    import src.cli as cli
    _reload(cli, monkeypatch)
    monkeypatch.setattr("src.cli.shutil.which", lambda _: "agy")

    def fake_run(cmd, **kwargs):
        return SimpleNamespace(returncode=1, stdout="", stderr="something went wrong")

    monkeypatch.setattr("src.cli.subprocess.run", fake_run)
    result = cli.execute_antigravity_simple("Hello", str(tmp_path))
    assert "Antigravity CLI Error: something went wrong" in result


def test_simple_timeout_expired(tmp_path, monkeypatch):
    import src.cli as cli
    _reload(cli, monkeypatch)
    monkeypatch.setattr("src.cli.shutil.which", lambda _: "agy")

    def fake_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=kwargs["timeout"])

    monkeypatch.setattr("src.cli.subprocess.run", fake_run)
    result = cli.execute_antigravity_simple("Hello", str(tmp_path))
    assert "timed out" in result


def test_simple_empty_output(tmp_path, monkeypatch):
    import src.cli as cli
    _reload(cli, monkeypatch)
    monkeypatch.setattr("src.cli.shutil.which", lambda _: "agy")

    def fake_run(cmd, **kwargs):
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("src.cli.subprocess.run", fake_run)
    result = cli.execute_antigravity_simple("Hello", str(tmp_path))
    assert "No output from Antigravity CLI" in result


def test_with_files_requires_files(tmp_path, monkeypatch):
    import src.cli as cli
    _reload(cli, monkeypatch)
    monkeypatch.setattr("src.cli.shutil.which", lambda _: "agy")
    result = cli.execute_antigravity_with_files("Hello", str(tmp_path), files_list=None)
    assert "No files provided" in result


def test_with_files_inline_mode(tmp_path, monkeypatch):
    import src.cli as cli
    _reload(cli, monkeypatch)
    monkeypatch.setattr("src.cli.shutil.which", lambda _: "agy")
    f = tmp_path / "example.txt"
    f.write_text("content", encoding="utf-8")

    def fake_run(cmd, cwd, capture_output, text, timeout):
        assert "--print" in cmd
        assert "=== example.txt ===" in " ".join(cmd)
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr("src.cli.subprocess.run", fake_run)
    result = cli.execute_antigravity_with_files("Hello", str(tmp_path), files_list=["example.txt"])
    assert result == "ok"


def test_with_files_at_command_mode(tmp_path, monkeypatch):
    import src.cli as cli
    _reload(cli, monkeypatch)
    monkeypatch.setattr("src.cli.shutil.which", lambda _: "agy")
    f = tmp_path / "context" / "info.txt"
    f.parent.mkdir()
    f.write_text("data", encoding="utf-8")

    def fake_run(cmd, cwd, capture_output, text, timeout):
        assert "--print" in cmd
        assert "@context/info.txt" in " ".join(cmd)
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr("src.cli.subprocess.run", fake_run)
    result = cli.execute_antigravity_with_files("Hello", str(tmp_path), files_list=["context/info.txt"], mode="at_command")
    assert result == "ok"


def test_with_files_unsupported_mode(tmp_path, monkeypatch):
    import src.cli as cli
    _reload(cli, monkeypatch)
    monkeypatch.setattr("src.cli.shutil.which", lambda _: "agy")
    f = tmp_path / "test.txt"
    f.write_text("x", encoding="utf-8")
    result = cli.execute_antigravity_with_files("Hello", str(tmp_path), files_list=["test.txt"], mode="bad_mode")
    assert "Unsupported files mode" in result


def test_with_files_missing_file_shows_warnings(tmp_path, monkeypatch):
    import src.cli as cli
    _reload(cli, monkeypatch)
    monkeypatch.setattr("src.cli.shutil.which", lambda _: "agy")

    def fake_run(cmd, **kwargs):
        return SimpleNamespace(returncode=0, stdout="done", stderr="")

    monkeypatch.setattr("src.cli.subprocess.run", fake_run)
    result = cli.execute_antigravity_with_files("Hello", str(tmp_path), files_list=["missing.txt"])
    assert "Warnings" in result
    assert "Skipped missing file" in result
