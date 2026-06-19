"""Antigravity Bridge MCP tool definitions.

Exposes four tools (``agy_consult``, ``agy_consult_with_files``,
``agy_web_search``, ``agy_list_models``), reusable prompts, a config/version
resource, and argument completion — all bridging to the ``agy`` CLI.

SDK features in use: structured output (Pydantic :class:`AgyResult`), proper
``ToolError`` on failure, tool annotations + titles, client-side logging via
:class:`Context`, server ``instructions``, ``@mcp.prompt``, ``@mcp.resource``,
and ``@mcp.completion``.
"""

import json
import signal
import sys
from typing import Any

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.server.fastmcp.utilities.func_metadata import ArgModelBase
from mcp.types import Completion, ToolAnnotations
from pydantic import BaseModel, Field

from . import __version__, cli, config, observability, security

# NOTE: deliberately *no* ``from __future__ import annotations`` here. With
# postponed (string) annotations, FastMCP's ``Tool.from_function`` introspects
# the ``ctx`` parameter via ``inspect.signature`` and sees the *string*
# ``"Context[Any, Any, Any]"``; its ``issubclass(str, Context)`` check fails, so
# ``ctx`` is never flagged as the injected context kwarg. It then leaks into the
# tool's input schema as a *required* user argument and is never supplied, which
# makes **every** tool call fail with ``ctx - Field required``. Keeping the
# annotations real (resolved at definition time) lets that check succeed. Verify
# this stays true if ``ctx`` is ever retyped.
#
# Reject unknown/extra arguments on every tool. FastMCP builds each tool's
# argument model with ``__base__=ArgModelBase``; that base ignores extras by
# default (Pydantic ``extra="ignore"``), so unknown parameters are silently
# dropped. Forbidding them turns an unknown option into a hard error server-side
# and advertises ``additionalProperties: false`` in the tool's input schema so
# well-behaved clients reject it before even sending. This must run *before* any
# ``@mcp.tool`` registration, which snapshots the model config.
ArgModelBase.model_config["extra"] = "forbid"

# FastMCP's ``Context`` is generic over (ServerSessionT, LifespanContextT,
# RequestT); we don't specialise them, so bind each to Any for strict typing.
_Ctx = Context[Any, Any, Any]

# Surface usage guidance to MCP clients (shown by clients that render it).
_INSTRUCTIONS = (
    "Antigravity Bridge forwards prompts to the `agy` CLI (Antigravity). "
    "Use `agy_consult` for plain queries, `agy_consult_with_files` to attach "
    "file context, `agy_web_search` for current/web info, and "
    "`agy_list_models` to see selectable models. `agy` is stateless on this "
    "side; pass `conversation_id`/`continue_last` to resume an agy-held "
    "conversation. Tools return a structured `AgyResult`; failures raise an "
    "error result. Read `config://settings` for the live configuration."
)

mcp = FastMCP("antigravity-bridge", instructions=_INSTRUCTIONS)
# FastMCP's constructor does not accept a version kwarg (it is not part of
# ``Settings``), and without one the handshake falls back to the installed
# ``mcp`` SDK version. Set the underlying server's public ``version`` attribute
# to src.__version__ (the single source of truth) so ``initialize`` advertises
# the bridge's own version.
mcp._mcp_server.version = __version__


# ---------------------------------------------------------------------------
# Structured output model
# ---------------------------------------------------------------------------


class AgyResult(BaseModel):
    """Structured return value of every tool.

    ``output`` always carries the human-readable text (the model response on
    success). Tools raise a ``ToolError`` on failure rather than setting
    ``success=False``, so a returned ``AgyResult`` implies success.
    """

    success: bool
    output: str
    model: str = ""
    warnings: list[str] = Field(default_factory=list)
    duration_ms: float | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Best-effort cache of ``agy models`` output so completion/validation do not
# spawn a subprocess on every request. Refreshed only on process start.
_models_cache: list[str] | None = None


async def _fetch_model_names() -> list[str]:
    """Return the model names advertised by ``agy models`` (cached, best-effort).

    Returns an empty list on any failure (agy missing, auth error, etc.) so that
    :func:`_validate_model` degrades gracefully (skips validation) rather than
    blocking every request.
    """
    global _models_cache
    if _models_cache is not None:
        return _models_cache
    try:
        raw = await cli.execute_antigravity_models_async()
    except Exception:  # never let model lookup break the tool itself
        return []
    stripped = raw.strip()
    # Don't parse error messages or empty output as model names.
    if not stripped or stripped.lower().startswith("error:"):
        return []
    names = [line.strip() for line in stripped.splitlines() if line.strip()]
    _models_cache = names
    return names


def _validate_query(query: str) -> None:
    """Validate the prompt, raising :class:`ToolError` on failure."""
    try:
        security.validate_query(query, config.load_settings().max_query_length)
    except security.ValidationError as exc:
        raise ToolError(f"Invalid query: {exc}") from exc


async def _validate_model(model: str) -> None:
    """Validate that the model name is supported, raising ToolError if not."""
    if not model:
        return
    supported = await _fetch_model_names()
    if not supported:
        return
    if model not in supported:
        supported_str = ", ".join(f"'{m}'" for m in supported)
        raise ToolError(
            f"Model '{model}' is not supported. Supported models: {supported_str}"
        )


async def _notify(ctx: _Ctx | None, level: str, message: str) -> None:
    """Emit a log line both to the server logger and the MCP client UI."""
    getattr(observability.get_logger(), level, lambda m: None)(message)
    if ctx is not None:
        handler = getattr(ctx, level, None)
        if handler is not None:
            await handler(message)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool(
    name="agy_consult",
    title="Consult Antigravity (agy)",
    description="Send a query directly to the Antigravity CLI.",
    annotations=ToolAnnotations(readOnlyHint=False, openWorldHint=True),
    structured_output=True,
)
async def agy_consult(
    query: str,
    directory: str,
    ctx: _Ctx,
    timeout_seconds: int | None = None,
    model: str = "",
    add_dirs: list[str] | None = None,
    conversation_id: str = "",
    continue_last: bool = False,
) -> AgyResult:
    """Send a query directly to the Antigravity CLI.

    Args:
        query: Prompt text forwarded verbatim to the CLI.
        directory: Working directory used for command execution.
        ctx: MCP request context (injected; used for client logging).
        timeout_seconds: Optional per-call timeout override in seconds.
        model: Optional model override (e.g. ``"Claude Opus 4.6 (Thinking)"``).
        add_dirs: Extra directories to attach to the workspace.
        conversation_id: Resume a specific conversation by ID (stateless on our
            side; ``agy`` holds the conversation).
        continue_last: If True, continue the most recent conversation.

    Returns:
        An :class:`AgyResult` with the response text. Raises an MCP error on
        failure.
    """
    _validate_query(query)
    target_model = model or config.load_settings().model
    await _validate_model(target_model)
    used_model = target_model or "default"
    await _notify(
        ctx, "info", f"agy_consult: query ({len(query)} chars), model={used_model}"
    )
    outcome = await cli.execute_antigravity_simple_outcome_async(
        query,
        directory,
        timeout_seconds,
        model,
        tuple(add_dirs or ()),
        conversation_id,
        continue_last,
    )
    if not outcome.success:
        await _notify(ctx, "error", f"agy_consult failed: {outcome.output}")
        raise ToolError(outcome.output)
    await _notify(ctx, "info", f"agy_consult: done in {outcome.duration_ms} ms")
    return AgyResult(
        success=True,
        output=outcome.output,
        model=outcome.model,
        warnings=outcome.warnings,
        duration_ms=outcome.duration_ms,
    )


@mcp.tool(
    name="agy_consult_with_files",
    title="Consult Antigravity with files",
    description="Send a query to the Antigravity CLI with file context.",
    annotations=ToolAnnotations(readOnlyHint=False, openWorldHint=True),
    structured_output=True,
)
async def agy_consult_with_files(
    query: str,
    directory: str,
    files: list[str] | None,
    ctx: _Ctx,
    timeout_seconds: int | None = None,
    mode: str = "inline",
    model: str = "",
    add_dirs: list[str] | None = None,
    conversation_id: str = "",
    continue_last: bool = False,
) -> AgyResult:
    """Send a query to the Antigravity CLI with file context.

    Args:
        query: Prompt text forwarded to the CLI.
        directory: Working directory used for resolving relative file paths.
        files: Relative or absolute file paths to include alongside the prompt.
        ctx: MCP request context (injected).
        timeout_seconds: Optional per-call timeout override in seconds.
        mode: ``"inline"`` streams truncated snippets; ``"at_command"`` emits
            ``@path`` directives so Antigravity CLI resolves files itself.
        model: Optional model override.
        add_dirs: Extra directories to attach to the workspace.
        conversation_id: Resume a specific conversation by ID.
        continue_last: If True, continue the most recent conversation.

    Returns:
        An :class:`AgyResult`. Raises an MCP error on failure.
    """
    if not files:
        raise ToolError("files parameter is required for agy_consult_with_files")
    if mode.lower() not in {"inline", "at_command"}:
        raise ToolError(
            f"Unsupported files mode '{mode}'. Use 'inline' or 'at_command'."
        )
    _validate_query(query)
    target_model = model or config.load_settings().model
    await _validate_model(target_model)
    await _notify(
        ctx,
        "info",
        f"agy_consult_with_files: {len(files)} file(s), mode={mode}",
    )
    outcome = await cli.execute_antigravity_with_files_outcome_async(
        query,
        directory,
        files,
        timeout_seconds,
        mode,
        model,
        tuple(add_dirs or ()),
        conversation_id,
        continue_last,
    )
    if not outcome.success:
        await _notify(ctx, "error", f"agy_consult_with_files failed: {outcome.output}")
        raise ToolError(outcome.output)
    await _notify(
        ctx, "info", f"agy_consult_with_files: done in {outcome.duration_ms} ms"
    )
    return AgyResult(
        success=True,
        output=outcome.output,
        model=outcome.model,
        warnings=outcome.warnings,
        duration_ms=outcome.duration_ms,
    )


@mcp.tool(
    name="agy_web_search",
    title="Antigravity web search",
    description="Ask Antigravity queries with web search context.",
    annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True),
    structured_output=True,
)
async def agy_web_search(
    query: str,
    ctx: _Ctx,
    directory: str,
    timeout_seconds: int | None = None,
    model: str = "",
    add_dirs: list[str] | None = None,
    conversation_id: str = "",
    continue_last: bool = False,
) -> AgyResult:
    """Ask Antigravity queries with web search context.

    Uses Antigravity CLI's automatic web search capability. The model decides
    when to search based on query context (best-effort, not guaranteed).

    Args:
        query: Search query or question to look up on the web.
        ctx: MCP request context (injected).
        directory: Working directory for command execution.
        timeout_seconds: Optional per-call timeout override in seconds.
        model: Optional model override.
        add_dirs: Extra directories to attach to the workspace.
        conversation_id: Resume a specific conversation by ID.
        continue_last: If True, continue the most recent conversation.

    Returns:
        An :class:`AgyResult` with the response (and any web sources).
    """
    search_prompt = f"Please use web search to find current information about: {query}"
    # Validate the prompt actually forwarded to the CLI (the bridge-internal
    # prefix counts toward the limit), not just the raw user query.
    _validate_query(search_prompt)
    target_model = model or config.load_settings().model
    await _validate_model(target_model)
    await _notify(ctx, "info", f"agy_web_search: query ({len(query)} chars)")
    outcome = await cli.execute_antigravity_simple_outcome_async(
        search_prompt,
        directory,
        timeout_seconds,
        model,
        tuple(add_dirs or ()),
        conversation_id,
        continue_last,
    )
    if not outcome.success:
        await _notify(ctx, "error", f"agy_web_search failed: {outcome.output}")
        raise ToolError(outcome.output)
    await _notify(ctx, "info", f"agy_web_search: done in {outcome.duration_ms} ms")
    return AgyResult(
        success=True,
        output=outcome.output,
        model=outcome.model,
        warnings=outcome.warnings,
        duration_ms=outcome.duration_ms,
    )


@mcp.tool(
    name="agy_list_models",
    title="List Antigravity models",
    description="List the models available to the Antigravity CLI.",
    annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False),
    structured_output=True,
)
async def agy_list_models(ctx: _Ctx) -> AgyResult:
    """List the models available to the Antigravity CLI.

    Args:
        ctx: MCP request context (injected).

    Returns:
        An :class:`AgyResult` whose ``output`` is the raw ``agy models`` text.
    """
    await _notify(ctx, "info", "agy_list_models: enumerating models")
    outcome = await cli.execute_antigravity_models_outcome_async()
    if not outcome.success:
        await _notify(ctx, "error", f"agy_list_models failed: {outcome.output}")
        raise ToolError(outcome.output)
    # Populate the shared cache as a side effect of a direct listing.
    global _models_cache
    _models_cache = [
        line.strip() for line in outcome.output.splitlines() if line.strip()
    ]
    await _notify(ctx, "info", f"agy_list_models: {len(_models_cache)} model(s)")
    return AgyResult(
        success=True,
        output=outcome.output,
        duration_ms=outcome.duration_ms,
    )


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------


@mcp.resource(
    "config://settings",
    name="settings",
    title="Bridge configuration",
    description="Live Antigravity Bridge settings and version (no secrets).",
)
def settings_resource() -> str:
    """Return the effective, non-secret configuration plus the package version."""
    s = config.load_settings()
    payload: dict[str, Any] = {
        "version": __version__,
        "default_timeout": s.default_timeout,
        "model": s.model,
        "skip_permissions": s.skip_permissions,
        "sandbox": s.sandbox,
        "health_check": s.health_check,
        "force_tty": s.force_tty,
        "align_print_timeout": s.align_print_timeout,
        "max_retries": s.max_retries,
        "retry_backoff_base": s.retry_backoff_base,
        "max_query_length": s.max_query_length,
        "allowed_dirs": list(s.allowed_dirs),
        "log_level": s.log_level,
        "log_format": s.log_format,
        "max_inline_file_count": s.max_inline_file_count,
        "max_inline_total_bytes": s.max_inline_total_bytes,
        "max_inline_file_bytes": s.max_inline_file_bytes,
    }
    return json.dumps(payload, indent=2, sort_keys=True)


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------


@mcp.prompt(
    name="investigate_project",
    title="Investigate a project",
    description="Build a thorough, assumption-free investigation prompt for a project directory.",
)
def investigate_project(directory: str, exclude: str = "") -> str:
    parts = [f"Perform a thorough investigation of the project at `{directory}`."]
    if exclude:
        parts.append(f"Exclude: {exclude}.")
    parts.append(
        "Cover architecture, module layout, dependencies, security posture, and "
        "anything noteworthy. Read the code directly — do not assume. Report "
        "findings as concise tables."
    )
    return "\n\n".join(parts)


@mcp.prompt(
    name="code_review",
    title="Review code",
    description="Build a focused code-review prompt for a directory.",
)
def code_review(directory: str, focus: str = "") -> str:
    parts = [
        f"Review the code in `{directory}` for correctness, robustness, and security."
    ]
    if focus:
        parts.append(f"Focus areas: {focus}.")
    parts.append(
        "Cite file:line for each finding and group by severity. No assumptions — "
        "verify against the actual code."
    )
    return "\n\n".join(parts)


@mcp.prompt(
    name="consult",
    title="Consult Antigravity",
    description="Wrap a query for agy_consult; the `model` argument autocompletes.",
)
def consult(query: str, model: str = "") -> str:
    prefix = f"[model: {model}] " if model else ""
    return f"{prefix}{query}"


# ---------------------------------------------------------------------------
# Completion
# ---------------------------------------------------------------------------


@mcp.completion()  # type: ignore[no-untyped-call,untyped-decorator]
async def _complete_arguments(
    ref: Any, argument: Any, context: Any
) -> Completion | None:
    """Autocomplete prompt ``model`` arguments from ``agy models``."""
    if getattr(argument, "name", None) == "model":
        return Completion(values=await _fetch_model_names())
    return None


# ---------------------------------------------------------------------------
# Server entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Entry point for the MCP server.

    Configures structured logging, validates configuration (fail-fast), installs
    graceful-shutdown signal handlers, then runs the FastMCP server.
    """
    observability.setup_logging(config.LOG_LEVEL, config.LOG_FORMAT)
    logger = observability.get_logger()

    try:
        config.validate_config()
    except config.ConfigError as exc:
        logger.error("configuration invalid: %s", exc, extra={"event": "config_error"})
        sys.exit(1)

    def _shutdown(signum: int, frame: object) -> None:
        logger.info(
            "shutdown signal received", extra={"event": "shutdown", "signal": signum}
        )
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    logger.info("starting antigravity-bridge", extra={"event": "startup"})
    try:
        mcp.run()
    except KeyboardInterrupt:
        logger.info("interrupted", extra={"event": "shutdown"})
