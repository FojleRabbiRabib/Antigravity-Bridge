# Repository Guidelines

## Project Structure & Module Organization
The package lives under `src/`, with `tools.py` defining the FastMCP tools and `__main__.py` exposing the module entry point. `config.py` holds all constants and environment variable reading. `cli.py` handles subprocess calls to `agy`. `files.py` manages file attachment preprocessing. Project metadata and the `antigravity-bridge` console script are declared in `pyproject.toml`.

## Build, Test, and Development Commands
- `pip install -e .` — install in editable mode for local development.
- `python3 -m src` — launch the MCP server directly; use `CTRL+C` to exit.
- `uvx antigravity-bridge` — run the packaged MCP server exactly as downstream clients will.
- `uvx --from build pyproject-build` — build distribution artifacts.
- `pytest` — run the full test suite.
Run commands from the project root to ensure relative paths resolve correctly.

## Prerequisites
- **Antigravity CLI**: `curl -fsSL https://antigravity.google/cli/install.sh | bash`
- **Verify**: `agy --version`

## Installation
- **Development**: `pip install -e .`
- **Production**: `pip install antigravity-bridge`
- **Claude Code**: `claude mcp add antigravity-bridge -s user -- uvx antigravity-bridge`

## Coding Style & Naming Conventions
Follow PEP 8 with 4-space indentation and an 88-character target line length. Use descriptive, lowercase `snake_case` for functions and variables, `UPPER_SNAKE_CASE` for constants, and reserve `CamelCase` for classes. Keep functions small, add docstrings describing intent, and include type hints on public interfaces. Use `python3` not `python` (system python may be v2). Use `from __future__ import annotations` in all modules for consistent type hint support. **Exception:** `src/tools.py` must NOT use it — with postponed (string) annotations, FastMCP cannot detect the injected `ctx: Context` parameter, leaks it into the tool's input schema as a required argument, and breaks every `tools/call` with `ctx - Field required`. Keep `tools.py`'s annotations real.

## Testing Guidelines
Validate changes by exercising all four MCP tools: `agy_consult`, `agy_consult_with_files`, `agy_web_search`, and `agy_list_models`. Run `python3 -m src` for the stdio server and `uvx antigravity-bridge --help` to confirm CLI wiring. Automated tests are located under `tests/`:
- `tests/test_config.py` — environment variable and timeout tests (covers all `ANTIGRAVITY_BRIDGE_*` env vars)
- `tests/test_cli.py` — CLI execution and error handling tests (CLI not found, auth errors, timeout, sandbox, skip-permissions)
- `tests/test_files.py` — file handling and truncation tests (inline payload, @-command, path resolution, missing files, limits)
- `tests/test_tools.py` — MCP tool registration and wiring tests (delegation, parameter validation, web search prepending)

## Commit & Pull Request Guidelines
Commit messages follow Conventional Commit prefixes (`feat:`, `fix:`, `chore:`, `docs:`) and should explain the motivation. Keep commits atomic and focused on one concern. Pull requests must include a concise summary, linked issues, and a brief testing log (commands run, expected vs. actual behavior).

## Security & Configuration
Use `ANTIGRAVITY_BRIDGE_*` environment variables for tuning (see CLAUDE.md for full table). Never commit `.env` files. Validate file paths carefully when adding features that read from disk. The project uses subprocess isolation for all CLI calls — no direct network exposure.
