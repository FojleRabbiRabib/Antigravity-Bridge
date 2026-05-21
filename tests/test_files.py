import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import src.files as files


@pytest.fixture(autouse=True)
def reset_config(monkeypatch):
    monkeypatch.delenv("ANTIGRAVITY_BRIDGE_MAX_INLINE_FILE_COUNT", raising=False)
    monkeypatch.delenv("ANTIGRAVITY_BRIDGE_MAX_INLINE_TOTAL_BYTES", raising=False)
    monkeypatch.delenv("ANTIGRAVITY_BRIDGE_MAX_INLINE_FILE_BYTES", raising=False)
    monkeypatch.delenv("ANTIGRAVITY_BRIDGE_INLINE_HEAD_BYTES", raising=False)
    monkeypatch.delenv("ANTIGRAVITY_BRIDGE_INLINE_TAIL_BYTES", raising=False)


def test_resolve_path_relative():
    abs_path, rel_path = files.resolve_path("/project", "src/main.py")
    assert abs_path == "/project/src/main.py"
    assert rel_path == "src/main.py"


def test_resolve_path_absolute():
    abs_path, rel_path = files.resolve_path("/project", "/other/file.py")
    assert abs_path == "/other/file.py"
    assert rel_path is None


def test_resolve_path_outside_directory():
    abs_path, rel_path = files.resolve_path("/project", "../secret/key.pem")
    assert rel_path is None


def test_read_file_small(tmp_path):
    f = tmp_path / "small.txt"
    f.write_text("hello world", encoding="utf-8")
    content, truncated, used = files.read_file_for_inline(str(f))
    assert content == "hello world"
    assert truncated is False
    assert used > 0


def test_read_file_truncated(tmp_path, monkeypatch):
    monkeypatch.setattr("src.config.MAX_INLINE_FILE_BYTES", 10)
    monkeypatch.setattr("src.config.INLINE_CHUNK_HEAD_BYTES", 4)
    monkeypatch.setattr("src.config.INLINE_CHUNK_TAIL_BYTES", 4)
    f = tmp_path / "big.txt"
    f.write_text("0123456789abcdefghij", encoding="utf-8")
    content, truncated, used = files.read_file_for_inline(str(f))
    assert truncated is True
    assert "[... truncated ...]" in content


def test_prepare_inline_payload_basic(tmp_path):
    f = tmp_path / "test.py"
    f.write_text("print('hello')", encoding="utf-8")
    payload, warnings = files.prepare_inline_payload(str(tmp_path), ["test.py"])
    assert "=== test.py ===" in payload
    assert "print('hello')" in payload
    assert len(warnings) == 0


def test_prepare_inline_payload_missing_file(tmp_path):
    payload, warnings = files.prepare_inline_payload(str(tmp_path), ["gone.txt"])
    assert "Skipped missing file: gone.txt" in warnings


def test_prepare_inline_payload_total_limit(tmp_path, monkeypatch):
    monkeypatch.setattr("src.config.MAX_INLINE_FILE_COUNT", 2)
    f1 = tmp_path / "a.txt"
    f2 = tmp_path / "b.txt"
    f3 = tmp_path / "c.txt"
    f1.write_text("a", encoding="utf-8")
    f2.write_text("b", encoding="utf-8")
    f3.write_text("c", encoding="utf-8")
    payload, warnings = files.prepare_inline_payload(str(tmp_path), ["a.txt", "b.txt", "c.txt"])
    assert "Inline file limit reached" in "\n".join(warnings)


def test_prepare_inline_payload_uses_antigravity_label(tmp_path, monkeypatch):
    monkeypatch.setattr("src.config.MAX_INLINE_FILE_BYTES", 5)
    monkeypatch.setattr("src.config.INLINE_CHUNK_HEAD_BYTES", 2)
    monkeypatch.setattr("src.config.INLINE_CHUNK_TAIL_BYTES", 2)
    f = tmp_path / "big.txt"
    f.write_text("0123456789", encoding="utf-8")
    payload, warnings = files.prepare_inline_payload(str(tmp_path), ["big.txt"])
    assert "[antigravity-bridge]" in payload


def test_prepare_at_command_prompt_basic(tmp_path):
    f = tmp_path / "src" / "app.py"
    f.parent.mkdir()
    f.write_text("code", encoding="utf-8")
    prompt, warnings = files.prepare_at_command_prompt(str(tmp_path), ["src/app.py"])
    assert "@src/app.py" in prompt
    assert len(warnings) == 0


def test_prepare_at_command_prompt_missing(tmp_path):
    prompt, warnings = files.prepare_at_command_prompt(str(tmp_path), ["nope.txt"])
    assert "No readable files" in "\n".join(warnings)


def test_prepare_at_command_prompt_outside_directory(tmp_path):
    prompt, warnings = files.prepare_at_command_prompt(str(tmp_path), ["/etc/passwd"])
    assert "Skipped file outside working directory" in "\n".join(warnings)
