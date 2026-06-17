"""Antigravity Bridge MCP tool definitions."""

from __future__ import annotations

import signal
import sys

from mcp.server.fastmcp import FastMCP

from . import __version__, cli, config, observability, security

mcp = FastMCP("antigravity-bridge")
# FastMCP's constructor does not accept a version kwarg (it is not part of
# ``Settings``), and without one the handshake falls back to the installed
# ``mcp`` SDK version. Set the underlying server's public ``version`` attribute
# to src.__version__ (the single source of truth) so ``initialize`` advertises
# the bridge's own version.
mcp._mcp_server.version = __version__


def _validate_query(query: str) -> str | None:
    """Return an error string if the query is invalid, else None."""
    try:
        security.validate_query(query, config.load_settings().max_query_length)
    except security.ValidationError as exc:
        return f"Error: {exc}"
    return None


@mcp.tool()
async def agy_consult(
    query: str,
    directory: str,
    timeout_seconds: int | None = None,
    model: str = "",
    add_dirs: list[str] | None = None,
    conversation_id: str = "",
    continue_last: bool = False,
) -> str:
    """Send a query directly to the Antigravity CLI.

    Args:
        query: Prompt text forwarded verbatim to the CLI.
        directory: Working directory used for command execution.
        timeout_seconds: Optional per-call timeout override in seconds.
        model: Optional model override (e.g. ``"gemini-3.5-flash"``).
        add_dirs: Extra directories to attach to the workspace.
        conversation_id: Resume a specific conversation by ID (stateless on our
            side; ``agy`` holds the conversation).
        continue_last: If True, continue the most recent conversation.

    Returns:
        Antigravity's response text or an explanatory error string.
    """
    err = _validate_query(query)
    if err:
        return err
    return await cli.execute_antigravity_simple_async(
        query,
        directory,
        timeout_seconds,
        model,
        tuple(add_dirs or ()),
        conversation_id,
        continue_last,
    )


@mcp.tool()
async def agy_consult_with_files(
    query: str,
    directory: str,
    files: list[str] | None = None,
    timeout_seconds: int | None = None,
    mode: str = "inline",
    model: str = "",
    add_dirs: list[str] | None = None,
    conversation_id: str = "",
    continue_last: bool = False,
) -> str:
    """Send a query to the Antigravity CLI with file context.

    Args:
        query: Prompt text forwarded to the CLI.
        directory: Working directory used for resolving relative file paths.
        files: Relative or absolute file paths to include alongside the prompt.
        timeout_seconds: Optional per-call timeout override in seconds.
        mode: ``"inline"`` streams truncated snippets; ``"at_command"`` emits
            ``@path`` directives so Antigravity CLI resolves files itself.
        model: Optional model override.
        add_dirs: Extra directories to attach to the workspace.
        conversation_id: Resume a specific conversation by ID.
        continue_last: If True, continue the most recent conversation.

    Returns:
        Antigravity's response or an explanatory error string with any warnings.
    """
    if not files:
        return "Error: files parameter is required for agy_consult_with_files"
    err = _validate_query(query)
    if err:
        return err
    return await cli.execute_antigravity_with_files_async(
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


@mcp.tool()
async def agy_web_search(
    query: str,
    directory: str = ".",
    timeout_seconds: int | None = None,
    model: str = "",
    add_dirs: list[str] | None = None,
    conversation_id: str = "",
    continue_last: bool = False,
) -> str:
    """Ask Antigravity queries with web search context.

    Note: This uses Antigravity CLI's automatic web search capability.
    The model determines when to search based on query context.
    Best-effort web search - not guaranteed for every query.

    Args:
        query: Search query or question to look up on the web.
        directory: Working directory for command execution.
        timeout_seconds: Optional per-call timeout override in seconds.
        model: Optional model override (e.g. ``"gemini-3.5-flash"``).
        add_dirs: Extra directories to attach to the workspace.
        conversation_id: Resume a specific conversation by ID (stateless on our
            side; ``agy`` holds the conversation).
        continue_last: If True, continue the most recent conversation.

    Returns:
        Antigravity's response with potential web sources
    """
    search_prompt = f"Please use web search to find current information about: {query}"
    return await cli.execute_antigravity_simple_async(
        search_prompt,
        directory,
        timeout_seconds,
        model,
        tuple(add_dirs or ()),
        conversation_id,
        continue_last,
    )


@mcp.tool()
async def agy_list_models() -> str:
    """List the models available to the Antigravity CLI.

    Returns:
        The raw ``agy models`` output, or an explanatory error string.
    """
    return await cli.execute_antigravity_models_async()


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
