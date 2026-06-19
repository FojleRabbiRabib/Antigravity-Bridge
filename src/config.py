"""Antigravity Bridge configuration.

Two access patterns coexist:
- Module-level constants (read once at import) for backward compatibility with
  callers like ``files.py`` that read ``config.MAX_INLINE_FILE_BYTES`` etc.
- A validated, frozen :class:`Settings` dataclass built by :func:`load_settings`,
  read fresh from the environment each call and used for fail-fast validation at
  startup (:func:`validate_config`) and structured access elsewhere.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from typing import Final

logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """Raised when configuration values are invalid (fail-fast at startup)."""


def _env_int(name: str, default: int) -> int:
    """Read an int env var at import; fall back to default on bad value.

    The module-level constants are read once at import time, before
    :func:`validate_config`/:func:`load_settings` can produce a clean
    :class:`ConfigError`. A stray non-numeric value would otherwise raise a raw
    ``ValueError`` and crash the server with an ugly traceback. This helper
    logs a warning and returns the default instead. The dynamic
    :func:`load_settings` path still raises :class:`ConfigError` (fail-fast).
    """
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        logger.warning(
            "Invalid %s value %r (must be integer). Using default %d.",
            name,
            raw,
            default,
        )
        return default


def _env_float(name: str, default: float) -> float:
    """Read a float env var at import; fall back to default on bad value.

    See :func:`_env_int` for rationale.
    """
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        logger.warning(
            "Invalid %s value %r (must be a number). Using default %s.",
            name,
            raw,
            default,
        )
        return default


# ---------------------------------------------------------------------------
# Backward-compatible module constants (read at import time)
# ---------------------------------------------------------------------------

DEFAULT_TIMEOUT: Final[int] = _env_int("ANTIGRAVITY_BRIDGE_DEFAULT_TIMEOUT", 600)
# Security: auto-skipping permissions is opt-in (default False).
SKIP_PERMISSIONS: Final[str] = os.getenv("ANTIGRAVITY_BRIDGE_SKIP_PERMISSIONS", "false")
SANDBOX: Final[str] = os.getenv("ANTIGRAVITY_BRIDGE_SANDBOX", "false")

MAX_INLINE_FILE_COUNT: Final[int] = _env_int(
    "ANTIGRAVITY_BRIDGE_MAX_INLINE_FILE_COUNT", 30
)
MAX_INLINE_TOTAL_BYTES: Final[int] = _env_int(
    "ANTIGRAVITY_BRIDGE_MAX_INLINE_TOTAL_BYTES", 1024 * 1024
)
MAX_INLINE_FILE_BYTES: Final[int] = _env_int(
    "ANTIGRAVITY_BRIDGE_MAX_INLINE_FILE_BYTES", 512 * 1024
)
INLINE_CHUNK_HEAD_BYTES: Final[int] = _env_int(
    "ANTIGRAVITY_BRIDGE_INLINE_HEAD_BYTES", 64 * 1024
)
INLINE_CHUNK_TAIL_BYTES: Final[int] = _env_int(
    "ANTIGRAVITY_BRIDGE_INLINE_TAIL_BYTES", 32 * 1024
)

# New capabilities (module-level mirrors for direct import where convenient).
MODEL: Final[str] = os.getenv("ANTIGRAVITY_BRIDGE_MODEL", "")
LOG_LEVEL: Final[str] = os.getenv("ANTIGRAVITY_BRIDGE_LOG_LEVEL", "INFO")
LOG_FORMAT: Final[str] = os.getenv("ANTIGRAVITY_BRIDGE_LOG_FORMAT", "text")
MAX_RETRIES: Final[int] = _env_int("ANTIGRAVITY_BRIDGE_MAX_RETRIES", 2)
RETRY_BACKOFF_BASE: Final[float] = _env_float(
    "ANTIGRAVITY_BRIDGE_RETRY_BACKOFF_BASE", 0.5
)
MAX_QUERY_LENGTH: Final[int] = _env_int("ANTIGRAVITY_BRIDGE_MAX_QUERY_LENGTH", 100000)
HEALTH_CHECK: Final[str] = os.getenv("ANTIGRAVITY_BRIDGE_HEALTH_CHECK", "true")
ALIGN_PRINT_TIMEOUT: Final[str] = os.getenv(
    "ANTIGRAVITY_BRIDGE_ALIGN_PRINT_TIMEOUT", "true"
)
# Run ``agy --print`` under a pseudo-TTY. agy's print mode hangs in non-TTY /
# headless subprocess environments (upstream bug #318), which is exactly how the
# bridge spawns it. Default on; can be disabled where PTYs are unavailable.
FORCE_TTY: Final[str] = os.getenv("ANTIGRAVITY_BRIDGE_FORCE_TTY", "true")


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

_TRUE_VALUES: Final[frozenset[str]] = frozenset({"1", "true", "yes", "on"})


def _parse_bool(raw: str) -> bool:
    return raw.strip().lower() in _TRUE_VALUES


def _parse_int(name: str, raw: str) -> int:
    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"{name} must be an integer, got: {raw!r}") from exc


def _parse_float(name: str, raw: str) -> float:
    try:
        return float(raw)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"{name} must be a number, got: {raw!r}") from exc


def _parse_allowed_dirs(raw: str) -> tuple[str, ...]:
    if not raw or not raw.strip():
        return ()
    parts = re.split(r"[,:]", raw)
    return tuple(p.strip() for p in parts if p.strip())


# ---------------------------------------------------------------------------
# Settings dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Settings:
    """Validated runtime configuration."""

    default_timeout: int
    skip_permissions: bool
    sandbox: bool
    model: str
    allowed_dirs: tuple[str, ...]
    log_level: str
    log_format: str
    max_retries: int
    retry_backoff_base: float
    max_query_length: int
    health_check: bool
    align_print_timeout: bool
    force_tty: bool
    max_inline_file_count: int
    max_inline_total_bytes: int
    max_inline_file_bytes: int
    inline_chunk_head_bytes: int
    inline_chunk_tail_bytes: int


def load_settings() -> Settings:
    """Build a :class:`Settings` from the current environment (fail-fast)."""
    default_timeout = _parse_int(
        "ANTIGRAVITY_BRIDGE_DEFAULT_TIMEOUT",
        os.getenv("ANTIGRAVITY_BRIDGE_DEFAULT_TIMEOUT", "600"),
    )
    if default_timeout <= 0:
        raise ConfigError("ANTIGRAVITY_BRIDGE_DEFAULT_TIMEOUT must be positive")

    max_retries = _parse_int(
        "ANTIGRAVITY_BRIDGE_MAX_RETRIES",
        os.getenv("ANTIGRAVITY_BRIDGE_MAX_RETRIES", "2"),
    )
    if max_retries < 0:
        raise ConfigError("ANTIGRAVITY_BRIDGE_MAX_RETRIES must be >= 0")

    max_query_length = _parse_int(
        "ANTIGRAVITY_BRIDGE_MAX_QUERY_LENGTH",
        os.getenv("ANTIGRAVITY_BRIDGE_MAX_QUERY_LENGTH", "100000"),
    )
    if max_query_length <= 0:
        raise ConfigError("ANTIGRAVITY_BRIDGE_MAX_QUERY_LENGTH must be positive")

    retry_backoff_base = _parse_float(
        "ANTIGRAVITY_BRIDGE_RETRY_BACKOFF_BASE",
        os.getenv("ANTIGRAVITY_BRIDGE_RETRY_BACKOFF_BASE", "0.5"),
    )
    if retry_backoff_base < 0:
        raise ConfigError("ANTIGRAVITY_BRIDGE_RETRY_BACKOFF_BASE must be >= 0")

    return Settings(
        default_timeout=default_timeout,
        skip_permissions=_parse_bool(
            os.getenv("ANTIGRAVITY_BRIDGE_SKIP_PERMISSIONS", "false")
        ),
        sandbox=_parse_bool(os.getenv("ANTIGRAVITY_BRIDGE_SANDBOX", "false")),
        model=os.getenv("ANTIGRAVITY_BRIDGE_MODEL", ""),
        allowed_dirs=_parse_allowed_dirs(
            os.getenv("ANTIGRAVITY_BRIDGE_ALLOWED_DIRS", "")
        ),
        log_level=os.getenv("ANTIGRAVITY_BRIDGE_LOG_LEVEL", "INFO"),
        log_format=os.getenv("ANTIGRAVITY_BRIDGE_LOG_FORMAT", "text"),
        max_retries=max_retries,
        retry_backoff_base=retry_backoff_base,
        max_query_length=max_query_length,
        health_check=_parse_bool(os.getenv("ANTIGRAVITY_BRIDGE_HEALTH_CHECK", "true")),
        align_print_timeout=_parse_bool(
            os.getenv("ANTIGRAVITY_BRIDGE_ALIGN_PRINT_TIMEOUT", "true")
        ),
        force_tty=_parse_bool(os.getenv("ANTIGRAVITY_BRIDGE_FORCE_TTY", "true")),
        max_inline_file_count=_parse_int(
            "ANTIGRAVITY_BRIDGE_MAX_INLINE_FILE_COUNT",
            os.getenv("ANTIGRAVITY_BRIDGE_MAX_INLINE_FILE_COUNT", "30"),
        ),
        max_inline_total_bytes=_parse_int(
            "ANTIGRAVITY_BRIDGE_MAX_INLINE_TOTAL_BYTES",
            os.getenv("ANTIGRAVITY_BRIDGE_MAX_INLINE_TOTAL_BYTES", str(1024 * 1024)),
        ),
        max_inline_file_bytes=_parse_int(
            "ANTIGRAVITY_BRIDGE_MAX_INLINE_FILE_BYTES",
            os.getenv("ANTIGRAVITY_BRIDGE_MAX_INLINE_FILE_BYTES", str(512 * 1024)),
        ),
        inline_chunk_head_bytes=_parse_int(
            "ANTIGRAVITY_BRIDGE_INLINE_HEAD_BYTES",
            os.getenv("ANTIGRAVITY_BRIDGE_INLINE_HEAD_BYTES", str(64 * 1024)),
        ),
        inline_chunk_tail_bytes=_parse_int(
            "ANTIGRAVITY_BRIDGE_INLINE_TAIL_BYTES",
            os.getenv("ANTIGRAVITY_BRIDGE_INLINE_TAIL_BYTES", str(32 * 1024)),
        ),
    )


def validate_config() -> Settings:
    """Eagerly validate configuration; raises :class:`ConfigError` (fail-fast)."""
    return load_settings()


# ---------------------------------------------------------------------------
# Backward-compatible helper functions
# ---------------------------------------------------------------------------


def get_timeout() -> int:
    timeout_str = os.getenv("ANTIGRAVITY_BRIDGE_TIMEOUT")
    if not timeout_str:
        # Use the freshly-read Settings value (the same one advertised via
        # config://settings) so the effective default matches the documented
        # one. Fall back to the import-time constant if the env is malformed
        # (load_settings would raise ConfigError), preserving the fail-soft
        # contract used by the module-level constants.
        try:
            return load_settings().default_timeout
        except ConfigError:
            return DEFAULT_TIMEOUT
    try:
        timeout = int(timeout_str)
        if timeout <= 0:
            logging.warning(
                "Invalid ANTIGRAVITY_BRIDGE_TIMEOUT value '%s' (must be positive). Using default %d seconds.",
                timeout_str,
                DEFAULT_TIMEOUT,
            )
            return DEFAULT_TIMEOUT
        return timeout
    except ValueError:
        logging.warning(
            "Invalid ANTIGRAVITY_BRIDGE_TIMEOUT value '%s' (must be integer). Using default %d seconds.",
            timeout_str,
            DEFAULT_TIMEOUT,
        )
        return DEFAULT_TIMEOUT


def coerce_timeout(timeout_seconds: int | None) -> int:
    """Coerce a per-call timeout override into a positive int.

    Defensive: tolerates stray string/float values from callers and falls back
    to the configured default on anything non-positive or non-int-like.
    """
    if timeout_seconds is None:
        return get_timeout()
    try:
        timeout = int(timeout_seconds)
    except (TypeError, ValueError):
        logging.warning(
            "Invalid timeout override '%s' (must be integer). Using default.",
            timeout_seconds,
        )
        return get_timeout()
    if timeout <= 0:
        logging.warning(
            "Invalid timeout override '%s' (must be positive). Using default.",
            timeout_seconds,
        )
        return get_timeout()
    return timeout


def should_skip_permissions() -> bool:
    return _parse_bool(SKIP_PERMISSIONS)


def should_sandbox() -> bool:
    return _parse_bool(SANDBOX)
