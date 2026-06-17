"""Antigravity Bridge file handling — inline payloads, @-command prep, truncation.

All path resolution goes through :mod:`src.security` so files that escape the
working directory (including via symlinks) are rejected, and binary files are
skipped rather than dumped into the prompt.
"""

from __future__ import annotations

from pathlib import Path

from . import config, security


def resolve_path(directory: str, candidate: str) -> tuple[str, str | None]:
    """Return absolute path and a relative display path rooted at ``directory``.

    Returns ``(abs_path, None)`` when the candidate escapes the working directory
    (after symlink resolution). Callers must treat a ``None`` relative path as
    "not safe to include".
    """
    try:
        abs_path, rel_path = security.resolve_within_root(directory, candidate)
    except security.SecurityError:
        return str(Path(candidate).resolve(strict=False)), None
    return str(abs_path), str(rel_path)


def read_file_for_inline(abs_path: str) -> tuple[str, bool, int]:
    """Read file with truncation safeguards.

    Returns tuple of (content, truncated flag, bytes_used).
    """
    abs_path_obj = Path(abs_path)
    size = abs_path_obj.stat().st_size
    truncated = False

    if size <= config.MAX_INLINE_FILE_BYTES:
        with abs_path_obj.open(encoding="utf-8", errors="ignore") as handle:
            content = handle.read()
        return content, truncated, min(size, config.MAX_INLINE_FILE_BYTES)

    truncated = True
    head_bytes = max(config.INLINE_CHUNK_HEAD_BYTES, 1)
    tail_bytes = max(config.INLINE_CHUNK_TAIL_BYTES, 0)

    with abs_path_obj.open("rb") as handle:
        head = handle.read(head_bytes)
        tail = b""
        if tail_bytes > 0 and size > head_bytes:
            handle.seek(max(size - tail_bytes, 0))
            tail = handle.read(tail_bytes)

    head_text = head.decode("utf-8", errors="ignore")
    tail_text = tail.decode("utf-8", errors="ignore") if tail else ""

    snippet = head_text
    if tail_text:
        snippet += "\n\n[... truncated ...]\n\n" + tail_text

    bytes_counted = min(size, config.MAX_INLINE_FILE_BYTES)
    return snippet, truncated, bytes_counted


def prepare_inline_payload(
    directory: str, files_list: list[str]
) -> tuple[str, list[str]]:
    """Return inline payload string and any warnings."""
    warnings: list[str] = []
    file_blocks: list[str] = []
    total_bytes = 0
    processed = 0

    if config.MAX_INLINE_FILE_COUNT <= 0:
        warnings.append("Inline attachments disabled via MAX_INLINE_FILE_COUNT<=0")
        return "", warnings

    for original_path in files_list:
        abs_path, rel_path = resolve_path(directory, original_path)

        if rel_path is None:
            warnings.append(f"Skipped file outside working directory: {original_path}")
            continue

        display_name = rel_path

        if not Path(abs_path).exists():
            warnings.append(f"Skipped missing file: {display_name}")
            continue

        if not Path(abs_path).is_file():
            warnings.append(f"Skipped non-regular file: {display_name}")
            continue

        if processed >= config.MAX_INLINE_FILE_COUNT:
            warnings.append(
                f"Inline file limit reached ({config.MAX_INLINE_FILE_COUNT}); skipped remaining attachments"
            )
            break

        if not security.is_text_file(abs_path):
            warnings.append(f"Skipped binary file: {display_name}")
            continue

        try:
            content, truncated, bytes_used = read_file_for_inline(abs_path)
        except Exception as exc:
            warnings.append(f"Error reading {display_name}: {exc}")
            continue

        if total_bytes + bytes_used > config.MAX_INLINE_TOTAL_BYTES:
            warnings.append(
                f"Inline payload exceeded {config.MAX_INLINE_TOTAL_BYTES} bytes; "
                f"skipped {display_name} and remaining attachments"
            )
            break

        block_header = f"=== {display_name} ==="
        if truncated:
            block_header += (
                "\n[antigravity-bridge] Content truncated for inline transfer"
            )
        file_blocks.append(f"{block_header}\n{content}")

        if truncated:
            warnings.append(
                f"Truncated {display_name}; only the first {config.INLINE_CHUNK_HEAD_BYTES}B "
                f"and last {config.INLINE_CHUNK_TAIL_BYTES}B were sent"
            )

        total_bytes += bytes_used
        processed += 1

    payload = "\n\n".join(file_blocks)
    return payload, warnings


def prepare_at_command_prompt(
    directory: str, files_list: list[str]
) -> tuple[str, list[str]]:
    """Return @-command prompt and any warnings."""
    warnings: list[str] = []
    prompt_lines: list[str] = []

    for original_path in files_list:
        abs_path, rel_path = resolve_path(directory, original_path)
        if rel_path is None:
            warnings.append(f"Skipped file outside working directory: {original_path}")
            continue
        if not Path(abs_path).exists():
            warnings.append(f"Skipped missing file: {original_path}")
            continue
        prompt_lines.append(f"@{rel_path}")

    if not prompt_lines:
        warnings.append("No readable files resolved for @ command; prompt unchanged")

    prompt = "\n".join(prompt_lines)
    return prompt, warnings
