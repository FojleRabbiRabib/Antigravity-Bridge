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


def test_default_timeout_is_600():
    import src.config as cfg

    assert cfg.DEFAULT_TIMEOUT == 600


def test_get_timeout_defaults_to_600():
    import src.config as cfg

    assert cfg.get_timeout() == 600


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
    assert cfg.get_timeout() == 600
    assert "must be positive" in caplog.text


def test_get_timeout_invalid_string(monkeypatch, caplog):
    import src.config as cfg

    monkeypatch.delenv("ANTIGRAVITY_BRIDGE_DEFAULT_TIMEOUT", raising=False)
    importlib.reload(cfg)
    caplog.set_level("WARNING")
    monkeypatch.setenv("ANTIGRAVITY_BRIDGE_TIMEOUT", "abc")
    importlib.reload(cfg)
    assert cfg.get_timeout() == 600
    assert "must be integer" in caplog.text


def test_get_timeout_falls_back_when_default_malformed(monkeypatch):
    # A non-integer DEFAULT_TIMEOUT makes load_settings() raise ConfigError; the
    # no-override branch must catch it and fall back to the import-time constant
    # (itself 600 via _env_int's fail-soft path) rather than crashing.
    import src.config as cfg

    monkeypatch.delenv("ANTIGRAVITY_BRIDGE_TIMEOUT", raising=False)
    monkeypatch.setenv("ANTIGRAVITY_BRIDGE_DEFAULT_TIMEOUT", "abc")
    importlib.reload(cfg)
    assert cfg.get_timeout() == 600


def test_coerce_timeout_none_returns_default():
    import src.config as cfg

    assert cfg.coerce_timeout(None) == 600


def test_coerce_timeout_valid():
    import src.config as cfg

    assert cfg.coerce_timeout(60) == 60


def test_coerce_timeout_invalid_falls_back():
    import src.config as cfg

    assert cfg.coerce_timeout(-1) == 600
    assert cfg.coerce_timeout("bad") == 600


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


_NEW_ENV_VARS = [
    "ANTIGRAVITY_BRIDGE_MODEL",
    "ANTIGRAVITY_BRIDGE_ALLOWED_DIRS",
    "ANTIGRAVITY_BRIDGE_LOG_LEVEL",
    "ANTIGRAVITY_BRIDGE_LOG_FORMAT",
    "ANTIGRAVITY_BRIDGE_MAX_RETRIES",
    "ANTIGRAVITY_BRIDGE_RETRY_BACKOFF_BASE",
    "ANTIGRAVITY_BRIDGE_MAX_QUERY_LENGTH",
    "ANTIGRAVITY_BRIDGE_HEALTH_CHECK",
    "ANTIGRAVITY_BRIDGE_ALIGN_PRINT_TIMEOUT",
]


@pytest.fixture(autouse=True)
def _clear_new_env(monkeypatch):
    for var in _NEW_ENV_VARS:
        monkeypatch.delenv(var, raising=False)


def test_settings_defaults():
    from src.config import load_settings

    s = load_settings()
    assert s.skip_permissions is True
    assert s.sandbox is False
    assert s.model == ""
    assert s.allowed_dirs == ()
    assert s.max_retries == 2
    assert s.retry_backoff_base == 0.5
    assert s.max_query_length == 100000
    assert s.health_check is True
    assert s.align_print_timeout is True
    assert s.log_level == "INFO"
    assert s.log_format == "text"
    assert s.default_timeout == 600


def test_settings_skip_permissions_can_disable(monkeypatch):
    monkeypatch.setenv("ANTIGRAVITY_BRIDGE_SKIP_PERMISSIONS", "false")
    from src.config import load_settings

    assert load_settings().skip_permissions is False


def test_settings_allowed_dirs_parsed(monkeypatch):
    monkeypatch.setenv("ANTIGRAVITY_BRIDGE_ALLOWED_DIRS", "/a:/b, /c")
    from src.config import load_settings

    assert load_settings().allowed_dirs == ("/a", "/b", "/c")


def test_settings_model_and_log(monkeypatch):
    monkeypatch.setenv("ANTIGRAVITY_BRIDGE_MODEL", "gemini-3.5-flash")
    monkeypatch.setenv("ANTIGRAVITY_BRIDGE_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("ANTIGRAVITY_BRIDGE_LOG_FORMAT", "json")
    from src.config import load_settings

    s = load_settings()
    assert s.model == "gemini-3.5-flash"
    assert s.log_level == "DEBUG"
    assert s.log_format == "json"


def test_settings_bad_int_raises(monkeypatch):
    monkeypatch.setenv("ANTIGRAVITY_BRIDGE_DEFAULT_TIMEOUT", "notanint")
    import pytest as _pytest

    from src.config import ConfigError, load_settings

    with _pytest.raises(ConfigError):
        load_settings()


def test_settings_negative_timeout_raises(monkeypatch):
    monkeypatch.setenv("ANTIGRAVITY_BRIDGE_DEFAULT_TIMEOUT", "-5")
    import pytest as _pytest

    from src.config import ConfigError, load_settings

    with _pytest.raises(ConfigError):
        load_settings()


def test_settings_bad_retries_raises(monkeypatch):
    monkeypatch.setenv("ANTIGRAVITY_BRIDGE_MAX_RETRIES", "abc")
    import pytest as _pytest

    from src.config import ConfigError, load_settings

    with _pytest.raises(ConfigError):
        load_settings()


def test_validate_config_returns_settings():
    from src.config import Settings, validate_config

    assert isinstance(validate_config(), Settings)


def test_module_constants_fallback_on_bad_default_timeout(monkeypatch):
    """CORR-02: bad env value at import falls back to default instead of crashing."""
    import src.config as cfg

    monkeypatch.setenv("ANTIGRAVITY_BRIDGE_DEFAULT_TIMEOUT", "abc")
    importlib.reload(cfg)
    assert cfg.DEFAULT_TIMEOUT == 600


def test_module_constants_fallback_on_bad_retries(monkeypatch):
    """CORR-02: bad retries env value falls back to default instead of crashing."""
    import src.config as cfg

    monkeypatch.setenv("ANTIGRAVITY_BRIDGE_MAX_RETRIES", "abc")
    importlib.reload(cfg)
    assert cfg.MAX_RETRIES == 2


def test_module_constants_fallback_on_bad_backoff(monkeypatch):
    """CORR-02: bad backoff env value falls back to default instead of crashing."""
    import src.config as cfg

    monkeypatch.setenv("ANTIGRAVITY_BRIDGE_RETRY_BACKOFF_BASE", "xyz")
    importlib.reload(cfg)
    assert cfg.RETRY_BACKOFF_BASE == 0.5
