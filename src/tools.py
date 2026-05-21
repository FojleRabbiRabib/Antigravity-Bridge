"""Antigravity Bridge MCP tool definitions."""

from __future__ import annotations

from . import cli

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("antigravity-bridge")


@mcp.tool()
def agy_consult(
    query: str,
    directory: str,
    timeout_seconds: int | None = None,
) -> str:
    """Send a query directly to the Antigravity CLI.

    Args:
        query: Prompt text forwarded verbatim to the CLI.
        directory: Working directory used for command execution.
        timeout_seconds: Optional per-call timeout override in seconds.

    Returns:
        Antigravity's response text or an explanatory error string.
    """
    return cli.execute_antigravity_simple(query, directory, timeout_seconds)


@mcp.tool()
def agy_consult_with_files(
    query: str,
    directory: str,
    files: list[str] | None = None,
    timeout_seconds: int | None = None,
    mode: str = "inline",
) -> str:
    """Send a query to the Antigravity CLI with file context.

    Args:
        query: Prompt text forwarded to the CLI.
        directory: Working directory used for resolving relative file paths.
        files: Relative or absolute file paths to include alongside the prompt.
        timeout_seconds: Optional per-call timeout override in seconds.
        mode: ``"inline"`` streams truncated snippets; ``"at_command"`` emits
            ``@path`` directives so Antigravity CLI resolves files itself.

    Returns:
        Antigravity's response or an explanatory error string with any warnings.
    """
    if not files:
        return "Error: files parameter is required for agy_consult_with_files"
    return cli.execute_antigravity_with_files(query, directory, files, timeout_seconds, mode)


@mcp.tool()
def agy_web_search(
    query: str,
    directory: str = ".",
    timeout_seconds: int | None = None,
) -> str:
    """Ask Antigravity queries with web search context.

    Note: This uses Antigravity CLI's automatic web search capability.
    The model determines when to search based on query context.
    Best-effort web search - not guaranteed for every query.

    Args:
        query: Search query or question to look up on the web
        directory: Working directory for command execution
        timeout_seconds: Optional per-call timeout override in seconds

    Returns:
        Antigravity's response with potential web sources
    """
    search_prompt = f"Please use web search to find current information about: {query}"
    return cli.execute_antigravity_simple(search_prompt, directory, timeout_seconds)


def main():
    """Entry point for the MCP server."""
    mcp.run()
