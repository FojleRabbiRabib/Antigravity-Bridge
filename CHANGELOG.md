# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.1] - 2026-06-17

### Fixed
- **Health-check subprocess leak on Python 3.11+**: `ensure_healthy` now handles `asyncio.TimeoutError` before `OSError`. On Python 3.11+ `asyncio.TimeoutError` aliases the builtin `TimeoutError` (a subclass of `OSError`), so the broader `OSError` handler previously swallowed the timeout and the probe process was never killed. (Passed on 3.10, where `asyncio.TimeoutError` is a distinct class.)

### Changed (CI)
- Lint job installs the project so `mypy` (strict) resolves the `mcp` package types instead of treating `@mcp.tool()` as an untyped decorator.
- Tests: prefixed unused unpacked variables (`ruff` RUF059).

---

## [1.1.0] - 2026-06-17

### Added
- **New tool `agy_list_models`** — exposes the `agy models` subcommand so clients can enumerate available models.
- **Model selection** — `agy_consult` and `agy_consult_with_files` accept a `model` parameter; global default via `ANTIGRAVITY_BRIDGE_MODEL`.
- **Conversation continuation** — both consult tools accept `conversation_id` and `continue_last` (forwarded as `--conversation` / `--continue`). The server stays stateless; `agy` holds the conversation.
- **Extra workspace directories** — `add_dirs` parameter attaches additional `--add-dir` workspaces.
- **`--print-timeout` alignment** — agy's internal print-mode wait is now aligned with the per-call timeout, preventing mid-run SIGKILLs.
- **Async execution core** — CLI execution uses `asyncio.create_subprocess_exec`; MCP tools are async and non-blocking. Sync wrappers preserve the existing public API.
- **Health-check preflight** — cached one-time `agy --version` probe (`ANTIGRAVITY_BRIDGE_HEALTH_CHECK`, default on).
- **Bounded retry with exponential backoff** on transient failures only (`ANTIGRAVITY_BRIDGE_MAX_RETRIES`, `ANTIGRAVITY_BRIDGE_RETRY_BACKOFF_BASE`). Authentication and non-transient errors are never retried.
- **Observability** — structured logging (text/JSON via `ANTIGRAVITY_BRIDGE_LOG_LEVEL` / `ANTIGRAVITY_BRIDGE_LOG_FORMAT`), per-call request IDs, and `agy.call` metrics (duration, success, timeout).
- **Security module** — path containment (symlink-aware), directory allowlisting (`ANTIGRAVITY_BRIDGE_ALLOWED_DIRS`, default empty = unrestricted), query length/control-character validation (`ANTIGRAVITY_BRIDGE_MAX_QUERY_LENGTH`), and binary-file skipping in inline mode.
- **Graceful shutdown** — `SIGTERM`/`SIGINT` handlers and fail-fast config validation at startup.
- **Tooling** — ruff, black, mypy (strict), and pytest-cov (≥90% gate) configured; CI now runs lint + type + coverage across Python 3.10–3.13.
- **Typed command builder** — `src/command.py` centralizes `agy` argv construction.

### Changed
- **`ANTIGRAVITY_BRIDGE_SKIP_PERMISSIONS` now defaults to `false`** (security). MCP automation users opt in explicitly.
- Version is now a single source of truth (`dynamic = ["version"]` read from `src.__version__`).

### Fixed
- **Inline-mode path escape** — `prepare_inline_payload` no longer reads files that resolve outside the working directory (including via symlinks).
- **agy/subprocess timeout mismatch** — resolved by passing `--print-timeout`.

---

## [1.0.2] - 2026-05-22

### Fixed
- **Subprocess stdin conflict**: Added `stdin=subprocess.DEVNULL` to `agy` subprocess calls to prevent deadlock when running inside MCP stdio transport. Without this fix, `agy` could try to read from the MCP server's stdin, causing timeouts.

---

## [1.0.1] - 2026-05-22

### Fixed
- **Package entry point**: Renamed console script from `agy` to `antigravity-bridge`. The previous name caused `uvx agy` to look for a non-existent PyPI package instead of `antigravity-bridge`.
- **Minimum Python version**: Bumped from 3.9 to 3.10. The `mcp>=1.0.0` dependency requires Python >=3.10.
- **Legacy license classifier**: Removed `License :: OSI Approved :: Apache Software License` classifier per PEP 639 (SPDX `license = "Apache-2.0"` is sufficient).

### Changed
- Updated all documentation, MCP client configs, and CI workflows to reflect the new entry point name.

---

## [1.0.0] - 2026-05-22

### Added

#### Core Features
- **MCP Server**: Complete Model Context Protocol server bridging AI coding assistants to Antigravity AI
- **Three MCP Tools**:
  - `agy_consult` — Direct Antigravity CLI bridge for simple queries
  - `agy_consult_with_files` — CLI bridge with file attachment support for detailed analysis
  - `agy_web_search` — Antigravity CLI web search integration for current information
- **CLI Integration**: Direct subprocess integration with the official Antigravity CLI (`agy --print`)
- **Stateless Operation**: No session management, caching, or complex state — every call is independent

#### Attachment Guardrails
- **Inline mode**: Streams truncated file snippets with configurable byte/quantity caps
- **@-command mode**: Delegates `@path` expansion to Antigravity CLI for large context loads
- **Per-call timeout overrides**: MCP tools accept `timeout_seconds` to extend execution time
- **Truncation warnings**: Surface inline truncation warnings when file limits are reached

#### Configuration
- `ANTIGRAVITY_BRIDGE_TIMEOUT` — global default timeout override (default: 120 seconds)
- `ANTIGRAVITY_BRIDGE_DEFAULT_TIMEOUT` — module-level default timeout
- `ANTIGRAVITY_BRIDGE_SKIP_PERMISSIONS` — auto-skip trust prompt for MCP environments (default: true)
- `ANTIGRAVITY_BRIDGE_SANDBOX` — enable sandbox mode (default: false)
- `ANTIGRAVITY_BRIDGE_MAX_INLINE_FILE_COUNT` — max number of inline files (default: 30)
- `ANTIGRAVITY_BRIDGE_MAX_INLINE_TOTAL_BYTES` — max total inline payload (default: 1 MB)
- `ANTIGRAVITY_BRIDGE_MAX_INLINE_FILE_BYTES` — max per-file inline size (default: 512 KB)
- `ANTIGRAVITY_BRIDGE_INLINE_HEAD_BYTES` — head chunk for truncated files (default: 64 KB)
- `ANTIGRAVITY_BRIDGE_INLINE_TAIL_BYTES` — tail chunk for truncated files (default: 32 KB)

#### Deployment & Installation
- **uvx Support**: `uvx antigravity-bridge` for zero-install production deployment
- **pip install**: `pip install antigravity-bridge` for traditional installation
- **Development Mode**: `pip install -e .` for local source development
- **Module Execution**: `python3 -m src` for running the MCP server directly

#### Documentation & Community
- Comprehensive README with multi-client configuration (Claude Code, Cursor, VS Code, Windsurf, Cline, Void, Cherry Studio, Augment, Roo Code, Zencoder)
- CONTRIBUTING, SECURITY, and CODE_OF_CONDUCT policies
- Apache 2.0 License

### Architecture

#### Design Principles
- **CLI-First**: All AI queries go through subprocess calls to `agy --print`
- **Fail-Fast**: Clear error messages with actionable guidance
- **Zero Extra Dependencies**: Only `mcp>=1.0.0` required beyond Antigravity CLI

#### Module Structure
```
src/
├── __init__.py      # Package entry point and version
├── __main__.py      # Module execution entry point
├── config.py        # Configuration and environment variables
├── cli.py           # Antigravity CLI subprocess interface
├── files.py         # File attachment and preprocessing
└── tools.py         # MCP tool definitions
```

#### Security
- **Input Validation**: File path validation before disk reads
- **Process Isolation**: Subprocess execution for all CLI calls
- **No Network Exposure**: All network requests handled by Antigravity CLI
- **Minimal Attack Surface**: Stateless, simple architecture

---

## Links

- **Repository**: [https://github.com/FojleRabbiRabib/Antigravity-Bridge](https://github.com/FojleRabbiRabib/Antigravity-Bridge)
- **Issues**: [https://github.com/FojleRabbiRabib/Antigravity-Bridge/issues](https://github.com/FojleRabbiRabib/Antigravity-Bridge/issues)
- **MCP Protocol**: [https://modelcontextprotocol.io/](https://modelcontextprotocol.io/)

[1.1.1]: https://github.com/FojleRabbiRabib/Antigravity-Bridge/releases/tag/v1.1.1
[1.1.0]: https://github.com/FojleRabbiRabib/Antigravity-Bridge/releases/tag/v1.1.0
[1.0.2]: https://github.com/FojleRabbiRabib/Antigravity-Bridge/releases/tag/v1.0.2
[1.0.1]: https://github.com/FojleRabbiRabib/Antigravity-Bridge/releases/tag/v1.0.1
[1.0.0]: https://github.com/FojleRabbiRabib/Antigravity-Bridge/releases/tag/v1.0.0
