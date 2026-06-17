import os
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
    _abs_path, rel_path = files.resolve_path("/project", "../secret/key.pem")
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
    content, truncated, _used = files.read_file_for_inline(str(f))
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
    _payload, warnings = files.prepare_inline_payload(str(tmp_path), ["gone.txt"])
    assert "Skipped missing file: gone.txt" in warnings


def test_prepare_inline_payload_total_limit(tmp_path, monkeypatch):
    monkeypatch.setattr("src.config.MAX_INLINE_FILE_COUNT", 2)
    f1 = tmp_path / "a.txt"
    f2 = tmp_path / "b.txt"
    f3 = tmp_path / "c.txt"
    f1.write_text("a", encoding="utf-8")
    f2.write_text("b", encoding="utf-8")
    f3.write_text("c", encoding="utf-8")
    _payload, warnings = files.prepare_inline_payload(
        str(tmp_path), ["a.txt", "b.txt", "c.txt"]
    )
    assert "Inline file limit reached" in "\n".join(warnings)


def test_prepare_inline_payload_uses_antigravity_label(tmp_path, monkeypatch):
    monkeypatch.setattr("src.config.MAX_INLINE_FILE_BYTES", 5)
    monkeypatch.setattr("src.config.INLINE_CHUNK_HEAD_BYTES", 2)
    monkeypatch.setattr("src.config.INLINE_CHUNK_TAIL_BYTES", 2)
    f = tmp_path / "big.txt"
    f.write_text("0123456789", encoding="utf-8")
    payload, _warnings = files.prepare_inline_payload(str(tmp_path), ["big.txt"])
    assert "[antigravity-bridge]" in payload


def test_prepare_at_command_prompt_basic(tmp_path):
    f = tmp_path / "src" / "app.py"
    f.parent.mkdir()
    f.write_text("code", encoding="utf-8")
    prompt, warnings = files.prepare_at_command_prompt(str(tmp_path), ["src/app.py"])
    assert "@src/app.py" in prompt
    assert len(warnings) == 0


def test_prepare_at_command_prompt_missing(tmp_path):
    _prompt, warnings = files.prepare_at_command_prompt(str(tmp_path), ["nope.txt"])
    assert "No readable files" in "\n".join(warnings)


def test_prepare_at_command_prompt_outside_directory(tmp_path):
    _prompt, warnings = files.prepare_at_command_prompt(str(tmp_path), ["/etc/passwd"])
    assert "Skipped file outside working directory" in "\n".join(warnings)


def test_prepare_inline_payload_skips_binary(tmp_path):
    b = tmp_path / "x.bin"
    b.write_bytes(b"\x00\x01\x02PNG")
    payload, warnings = files.prepare_inline_payload(str(tmp_path), ["x.bin"])
    assert payload == ""
    assert any("binary" in w.lower() for w in warnings)


def test_prepare_inline_payload_skips_escape(tmp_path):
    # File outside the working directory must NOT be inlined (security hole fix).
    payload, warnings = files.prepare_inline_payload(
        str(tmp_path), ["../../../../etc/hostname"]
    )
    assert payload == ""
    assert any("outside working directory" in w.lower() for w in warnings)


def test_prepare_inline_payload_skips_escape_symlink(tmp_path):
    # A symlink inside the working dir that resolves OUTSIDE must be rejected.
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    target = tmp_path / "secret.txt"  # outside the sandbox working dir
    target.write_text("secret", encoding="utf-8")
    link = sandbox / "link.txt"
    link.symlink_to(target)
    payload, warnings = files.prepare_inline_payload(str(sandbox), ["link.txt"])
    assert payload == ""
    assert any("outside working directory" in w.lower() for w in warnings)


@pytest.mark.skipif(
    not hasattr(os, "mkfifo"), reason="mkfifo unavailable on this platform"
)
def test_prepare_inline_payload_skips_fifo(tmp_path):
    # A FIFO (named pipe) is a non-regular special file. Opening it BLOCKS until
    # a writer connects, which would hang the MCP event loop. The guard in
    # prepare_inline_payload must skip it before any open() call, so this test
    # returns in milliseconds rather than hanging.
    fifo = tmp_path / "pipe"
    os.mkfifo(str(fifo))

    payload, warnings = files.prepare_inline_payload(str(tmp_path), ["pipe"])

    assert payload == ""
    assert any("non-regular" in w.lower() for w in warnings)
