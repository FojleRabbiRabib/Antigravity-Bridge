import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(autouse=True)
def clear_env_vars(monkeypatch):
    monkeypatch.delenv("ANTIGRAVITY_BRIDGE_TIMEOUT", raising=False)
    monkeypatch.delenv("ANTIGRAVITY_BRIDGE_DEFAULT_TIMEOUT", raising=False)
    monkeypatch.delenv("ANTIGRAVITY_BRIDGE_SKIP_PERMISSIONS", raising=False)
    monkeypatch.delenv("ANTIGRAVITY_BRIDGE_SANDBOX", raising=False)


def test_default_timeout_is_120():
    import src.config as cfg
    assert cfg.DEFAULT_TIMEOUT == 120


def test_get_timeout_defaults_to_120():
    import src.config as cfg
    assert cfg.get_timeout() == 120


def test_get_timeout_with_custom_default(monkeypatch):
    import src.config as cfg
    monkeypatch.setenv("ANTIGRAVITY_BRIDGE_DEFAULT_TIMEOUT", "180")
    importlib.reload(cfg)
    assert cfg.get_timeout() == 180


def test_get_timeout_with_override(monkeypatch):
    import src.config as cfg
    monkeypatch.setenv("ANTIGRAVITY_BRIDGE_TIMEOUT", "90")
    importlib.reload(cfg)
    assert cfg.get_timeout() == 90


def test_get_timeout_override_priority(monkeypatch):
    import src.config as cfg
    monkeypatch.setenv("ANTIGRAVITY_BRIDGE_DEFAULT_TIMEOUT", "300")
    monkeypatch.setenv("ANTIGRAVITY_BRIDGE_TIMEOUT", "45")
    importlib.reload(cfg)
    assert cfg.get_timeout() == 45


def test_get_timeout_invalid_negative(monkeypatch, caplog):
    import src.config as cfg
    monkeypatch.delenv("ANTIGRAVITY_BRIDGE_DEFAULT_TIMEOUT", raising=False)
    importlib.reload(cfg)
    caplog.set_level("WARNING")
    monkeypatch.setenv("ANTIGRAVITY_BRIDGE_TIMEOUT", "-5")
    importlib.reload(cfg)
    assert cfg.get_timeout() == 120
    assert "must be positive" in caplog.text


def test_get_timeout_invalid_string(monkeypatch, caplog):
    import src.config as cfg
    monkeypatch.delenv("ANTIGRAVITY_BRIDGE_DEFAULT_TIMEOUT", raising=False)
    importlib.reload(cfg)
    caplog.set_level("WARNING")
    monkeypatch.setenv("ANTIGRAVITY_BRIDGE_TIMEOUT", "abc")
    importlib.reload(cfg)
    assert cfg.get_timeout() == 120
    assert "must be integer" in caplog.text


def test_coerce_timeout_none_returns_default():
    import src.config as cfg
    assert cfg.coerce_timeout(None) == 120


def test_coerce_timeout_valid():
    import src.config as cfg
    assert cfg.coerce_timeout(60) == 60


def test_coerce_timeout_invalid_falls_back():
    import src.config as cfg
    assert cfg.coerce_timeout(-1) == 120
    assert cfg.coerce_timeout("bad") == 120


def test_skip_permissions_defaults_true():
    import src.config as cfg
    assert cfg.should_skip_permissions() is True


def test_skip_permissions_disabled(monkeypatch):
    import src.config as cfg
    monkeypatch.setenv("ANTIGRAVITY_BRIDGE_SKIP_PERMISSIONS", "false")
    importlib.reload(cfg)
    assert cfg.should_skip_permissions() is False


def test_sandbox_defaults_false():
    import src.config as cfg
    assert cfg.should_sandbox() is False


def test_sandbox_enabled(monkeypatch):
    import src.config as cfg
    monkeypatch.setenv("ANTIGRAVITY_BRIDGE_SANDBOX", "true")
    importlib.reload(cfg)
    assert cfg.should_sandbox() is True


def test_inline_file_defaults():
    import src.config as cfg
    assert cfg.MAX_INLINE_FILE_COUNT == 30
    assert cfg.MAX_INLINE_TOTAL_BYTES == 1024 * 1024
    assert cfg.MAX_INLINE_FILE_BYTES == 512 * 1024
    assert cfg.INLINE_CHUNK_HEAD_BYTES == 64 * 1024
    assert cfg.INLINE_CHUNK_TAIL_BYTES == 32 * 1024
