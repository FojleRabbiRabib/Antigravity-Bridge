"""Security helpers: path containment, directory allowlisting, query validation.

These guardrails prevent the bridge from being directed at files or directories
outside an expected boundary, and reject malformed/oversized prompts.
"""

from __future__ import annotations

from pathlib import Path


class SecurityError(Exception):
    """Raised when a path or directory violates a containment/allowlist rule."""


class ValidationError(Exception):
    """Raised when user-supplied input (e.g. a query) fails validation."""


# Control characters permitted inside queries (whitespace).
_ALLOWED_CONTROL: frozenset[int] = frozenset({0x09, 0x0A, 0x0D})


def resolve_within_root(directory: str, candidate: str) -> tuple[Path, Path]:
    """Resolve ``candidate`` against ``directory`` and enforce containment.

    Symlinks are followed via :meth:`Path.resolve`, so a symlink that escapes the
    working directory is rejected after resolution (no TOCTOU on the raw path).

    Returns ``(abs_path, relative_path)``. Raises :class:`SecurityError` if the
    resolved path escapes the working directory.
    """
    root = Path(directory).resolve()
    cand = Path(candidate)
    cand_abs = cand if cand.is_absolute() else (root / cand)
    resolved = cand_abs.resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError as exc:  # path escapes root
        raise SecurityError(f"Path escapes working directory: {candidate}") from exc
    import os

    rel = Path(os.path.relpath(resolved, root))
    return resolved, rel


def check_allowed_directory(directory: str, allowed_dirs: tuple[str, ...]) -> None:
    """Ensure ``directory`` is within one of ``allowed_dirs``.

    An empty allowlist means unrestricted (the default), so full-project
    investigation is unaffected. When set, the working directory must resolve
    inside one of the allowed roots. Raises :class:`SecurityError` otherwise.
    """
    if not allowed_dirs:
        return
    target = Path(directory).resolve()
    for raw_root in allowed_dirs:
        root = Path(raw_root).resolve()
        try:
            target.relative_to(root)
            return
        except ValueError:
            continue
    raise SecurityError(f"Directory not in allowlist: {directory}")


def validate_query(query: str, max_length: int) -> str:
    """Validate a prompt before forwarding to the CLI.

    Rejects non-strings, oversized prompts, and control characters other than
    tab/newline/carriage-return. Returns the query unchanged on success.
    """
    if not isinstance(query, str):
        raise ValidationError("query must be a string")
    if len(query) > max_length:
        raise ValidationError(f"query exceeds max length {max_length}")
    for ch in query:
        code = ord(ch)
        if (
            code < 0x20 or code == 0x7F or 0x80 <= code <= 0x9F
        ) and code not in _ALLOWED_CONTROL:
            raise ValidationError(f"query contains control character (0x{code:02x})")
    return query


def is_text_file(path: str, sniff_bytes: int = 2048) -> bool:
    """Heuristically detect whether a file is text (NUL-byte sniff)."""
    try:
        with open(path, "rb") as handle:
            chunk = handle.read(sniff_bytes)
    except OSError:
        return False
    return b"\x00" not in chunk
