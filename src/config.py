"""Antigravity Bridge configuration."""

from __future__ import annotations

import logging
import os

DEFAULT_TIMEOUT = int(os.getenv("ANTIGRAVITY_BRIDGE_DEFAULT_TIMEOUT", "120"))
SKIP_PERMISSIONS = os.getenv("ANTIGRAVITY_BRIDGE_SKIP_PERMISSIONS", "true")
SANDBOX = os.getenv("ANTIGRAVITY_BRIDGE_SANDBOX", "false")

MAX_INLINE_FILE_COUNT = int(os.getenv("ANTIGRAVITY_BRIDGE_MAX_INLINE_FILE_COUNT", "30"))
MAX_INLINE_TOTAL_BYTES = int(os.getenv("ANTIGRAVITY_BRIDGE_MAX_INLINE_TOTAL_BYTES", str(1024 * 1024)))
MAX_INLINE_FILE_BYTES = int(os.getenv("ANTIGRAVITY_BRIDGE_MAX_INLINE_FILE_BYTES", str(512 * 1024)))
INLINE_CHUNK_HEAD_BYTES = int(os.getenv("ANTIGRAVITY_BRIDGE_INLINE_HEAD_BYTES", str(64 * 1024)))
INLINE_CHUNK_TAIL_BYTES = int(os.getenv("ANTIGRAVITY_BRIDGE_INLINE_TAIL_BYTES", str(32 * 1024)))


def get_timeout() -> int:
    timeout_str = os.getenv("ANTIGRAVITY_BRIDGE_TIMEOUT")
    if not timeout_str:
        return DEFAULT_TIMEOUT
    try:
        timeout = int(timeout_str)
        if timeout <= 0:
            logging.warning("Invalid ANTIGRAVITY_BRIDGE_TIMEOUT value '%s' (must be positive). Using default %d seconds.", timeout_str, DEFAULT_TIMEOUT)
            return DEFAULT_TIMEOUT
        return timeout
    except ValueError:
        logging.warning("Invalid ANTIGRAVITY_BRIDGE_TIMEOUT value '%s' (must be integer). Using default %d seconds.", timeout_str, DEFAULT_TIMEOUT)
        return DEFAULT_TIMEOUT


def coerce_timeout(timeout_seconds: int | None) -> int:
    if timeout_seconds is None:
        return get_timeout()
    try:
        timeout = int(timeout_seconds)
    except (TypeError, ValueError):
        logging.warning("Invalid timeout override '%s' (must be integer). Using default.", timeout_seconds)
        return get_timeout()
    if timeout <= 0:
        logging.warning("Invalid timeout override '%s' (must be positive). Using default.", timeout_seconds)
        return get_timeout()
    return timeout


def should_skip_permissions() -> bool:
    return SKIP_PERMISSIONS.lower() == "true"


def should_sandbox() -> bool:
    return SANDBOX.lower() == "true"
