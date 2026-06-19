# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Antigravity Bridge** is a lightweight MCP (Model Context Protocol) server that enables Claude Code to interact with Antigravity AI through the official `agy` CLI. The project follows extreme simplicity principles — doing ONE thing well: bridging Claude to Antigravity CLI.

**Key Characteristics:**
- Zero API costs (uses free Antigravity CLI)
- Stateless architecture with no session management
- Direct subprocess integration for optimal performance
- Inline file guardrails with optional delegation to Antigravity CLI's `@path` expansion
- Production-ready with professional CI/CD automation

## Development Commands

### Prerequisites
- **Antigravity CLI**: `curl -fsSL https://antigravity.google/cli/install.sh | bash`
- **Verify**: `agy --version`

### Installation & Setup

**Development Mode:**
```bash
git clone https://github.com/FojleRabbiRabib/Antigravity-Bridge.git
cd antigravity-bridge
pip install -e .
python3 -m src
```

**Production Installation:**
```bash
pip install antigravity-bridge
uvx antigravity-bridge
```

**Claude Code Integration:**
```bash
# Production (recommended)
claude mcp add antigravity-bridge -s user -- uvx antigravity-bridge

# Development
claude mcp add antigravity-bridge -s user -- python3 -m src
```

### Testing & Verification
```bash
# Run automated tests
pytest

# Verify package
python3 -c "import src; print(f'Antigravity Bridge v{src.__version__}')"
```

### Build & Distribution
```bash
rm -rf dist/ build/ *.egg-info
uvx --from build pyproject-build
pip install dist/*.whl
python3 -c "import src; print('Package works!')"
```

## Architecture

### Core Design Principles
- **CLI-First**: Direct subprocess calls to `agy --print`
- **Stateless**: Each tool call is independent with no session state
- **Adaptive Timeout**: Defaults to 120 seconds; override per call or via env var
- **Attachment Guardrails**: Inline mode enforces byte/quantity caps; `at_command` mode lets Antigravity CLI manage files
- **Fail-Fast**: Clear error messages with simple error handling
- **Zero Dependencies**: Only `mcp>=1.0.0` and external Antigravity CLI

### Module Structure
```
src/
├── __init__.py        # Package entry point, single-source version
├── __main__.py        # Module execution entry point
├── config.py          # Validated Settings + environment variables
├── security.py        # Path containment, allowlist, query/binary validation
├── files.py           # File attachment and preprocessing
├── command.py         # Typed agy argv builder (AgyCommand)
├── cli.py             # Async subprocess execution, retry, health check
├── observability.py   # Structured logging (text/JSON), request IDs, metrics
└── tools.py           # MCP tool definitions (FastMCP, async)
```

### Key Components

**`src/config.py`** — Configuration and environment variables
- All `ANTIGRAVITY_BRIDGE_*` environment variables with sensible defaults
- `Settings` frozen dataclass + `load_settings()` / `validate_config()` (fail-fast)
- `get_timeout()` / `coerce_timeout()` — timeout validation
- `should_skip_permissions()` / `should_sandbox()` — flag helpers

**`src/security.py`** — Security & validation
- `resolve_within_root()` — symlink-aware path containment
- `check_allowed_directory()` — directory allowlist (empty = unrestricted)
- `validate_query()` — length + control-character validation
- `is_text_file()` — NUL-byte binary detection

**`src/command.py`** — Typed argv builder
- `AgyCommand` dataclass → `.build()` assembles the full `agy` argv (model, add-dirs, `--print-timeout`, conversation)

**`src/cli.py`** — Async subprocess execution
- `execute_antigravity_simple_async()` / `execute_antigravity_with_files_async()` / `execute_antigravity_models_async()` — async core
- `execute_antigravity_simple()` / `execute_antigravity_with_files()` — sync wrappers (preserve public API)
- `_run_agy_async()` / `_run_with_retry()` / `ensure_healthy()` — execution, retry, preflight

**`src/files.py`** — File preprocessing
- `resolve_path()` — path resolution via `security` (rejects escapes/symlinks)
- `read_file_for_inline()` — read with head/tail truncation safeguards
- `prepare_inline_payload()` — build inline payload (skips binary + escaped files)
- `prepare_at_command_prompt()` — build `@path` directives

**`src/observability.py`** — Logging & metrics
- `setup_logging(level, fmt)` — text or JSON handler
- `new_request_id()` / `record_call()` / `get_logger()` — request IDs + structured metrics

**`src/tools.py`** — MCP tool definitions (FastMCP, async)
- `agy_consult()` — simple query tool
- `agy_consult_with_files()` — file context tool
- `agy_web_search()` — web search tool
- `agy_list_models()` — list available models
- `settings_resource()` — `config://settings` resource (live config + version)
- `investigate_project()` / `code_review()` / `consult()` — reusable prompt templates
- `_complete_arguments()` — `@mcp.completion` for `model` argument
- `AgyResult` — Pydantic structured output model; `_validate_query`/`_validate_model` helpers
- `main()` — logging init, config validation, signal handlers, `mcp.run()`
- SDK features in use: structured output, `ToolError` on failure, tool annotations + titles, `Context` client logging, server `instructions`, `@mcp.prompt`, `@mcp.resource`, `@mcp.completion`

### Configuration

All environment variables prefixed with `ANTIGRAVITY_BRIDGE_`:

| Variable | Default | Description |
|---|---|---|
| `ANTIGRAVITY_BRIDGE_TIMEOUT` | `600` | Global timeout override (seconds) |
| `ANTIGRAVITY_BRIDGE_DEFAULT_TIMEOUT` | `600` | Module-level default timeout |
| `ANTIGRAVITY_BRIDGE_SKIP_PERMISSIONS` | `true` | Add `--dangerously-skip-permissions`. Default **on** so consults/investigations actually run — agy print mode can't prompt for tool approvals, so without it a non-trivial query bails after planning (returns only the "I will…" narration). Set `false` **and** configure `ANTIGRAVITY_BRIDGE_ALLOWED_DIRS` to lock the server down. |
| `ANTIGRAVITY_BRIDGE_SANDBOX` | `false` | Enable sandbox mode |
| `ANTIGRAVITY_BRIDGE_MODEL` | _(agy default)_ | Default model override |
| `ANTIGRAVITY_BRIDGE_ALLOWED_DIRS` | _(empty = unrestricted)_ | Directory allowlist (comma/colon-separated) |
| `ANTIGRAVITY_BRIDGE_HEALTH_CHECK` | `true` | Cached `agy --version` preflight |
| `ANTIGRAVITY_BRIDGE_FORCE_TTY` | `false` | Run `agy --print` over plain pipes by default (reliable on current agy; a PTY forces TUI mode where agy can exit without flushing the response). Set `true` only if your agy build hangs headless (upstream bug #318, agy ≤1.0.6 / Windows). |
| `ANTIGRAVITY_BRIDGE_MAX_RETRIES` | `2` | Retries on transient failures |
| `ANTIGRAVITY_BRIDGE_RETRY_BACKOFF_BASE` | `0.5` | Exponential backoff base (s) |
| `ANTIGRAVITY_BRIDGE_MAX_QUERY_LENGTH` | `100000` | Max prompt length (chars) |
| `ANTIGRAVITY_BRIDGE_LOG_LEVEL` | `INFO` | Logging level |
| `ANTIGRAVITY_BRIDGE_LOG_FORMAT` | `text` | `text` or `json` |
| `ANTIGRAVITY_BRIDGE_MAX_INLINE_FILE_COUNT` | `30` | Max files in inline mode |
| `ANTIGRAVITY_BRIDGE_MAX_INLINE_TOTAL_BYTES` | `1048576` | Max total inline payload (1MB) |
| `ANTIGRAVITY_BRIDGE_MAX_INLINE_FILE_BYTES` | `524288` | Max per-file inline size (512KB) |
| `ANTIGRAVITY_BRIDGE_INLINE_HEAD_BYTES` | `65536` | Head chunk for truncated files (64KB) |
| `ANTIGRAVITY_BRIDGE_INLINE_TAIL_BYTES` | `32768` | Tail chunk for truncated files (32KB) |

## MCP Primitives

All four tools return a structured `AgyResult` (`{success, output, model, warnings, duration_ms}`) and raise a proper MCP `ToolError` on failure (rather than an error-as-string). Each tool carries annotations (`readOnlyHint`/`openWorldHint`) and a human-readable title, and logs start/done/error events to the MCP client via an injected `Context`.

**Argument strictness**: `ctx: Context` is auto-injected (never a user-facing arg). `src/tools.py` must **not** use `from __future__ import annotations` — with it, FastMCP fails to detect `ctx`, exposes it as a *required* schema field, and breaks every call. Unknown/extra arguments are rejected: the arg models are built with `extra="forbid"` (`ArgModelBase.model_config` patched before registration), so tool schemas carry `additionalProperties: false` and a stray parameter raises `ToolError`. `agy_consult_with_files` validates `mode` ∈ {`inline`, `at_command`} up front.

### `agy_consult`
- **Purpose**: Direct CLI bridge for simple queries (async)
- **Parameters**: `query`, `directory`, `timeout_seconds`, `model`, `add_dirs`, `conversation_id`, `continue_last`
- **Use Case**: General questions, code analysis without file attachments

### `agy_consult_with_files`
- **Purpose**: CLI bridge with file attachments for detailed analysis (async)
- **Parameters**: `query`, `directory`, `files`, `timeout_seconds`, `mode`, `model`, `add_dirs`, `conversation_id`, `continue_last`
- **Modes**: `"inline"` (default) or `"at_command"`
- **Use Case**: File-specific analysis, multi-file comparisons, code reviews

### `agy_web_search`
- **Purpose**: Web search queries with Antigravity CLI (async)
- **Parameters**: `query`, `directory`, `timeout_seconds`, `model`, `add_dirs`, `conversation_id`, `continue_last`
- **Use Case**: Current information, latest docs, recent changes

### `agy_list_models`
- **Purpose**: List models available to the Antigravity CLI (async, wraps `agy models`)
- **Parameters**: none
- **Use Case**: Discover selectable models before passing `model` to other tools

### Resource: `config://settings`
- Exposes the live, non-secret configuration and the package version as JSON.

### Prompts
- `investigate_project(directory, exclude)` — assumption-free investigation prompt
- `code_review(directory, focus)` — focused review prompt
- `consult(query, model)` — wraps a query; `model` autocompletes from `agy models`

### Model validation
- `agy_consult`, `agy_consult_with_files`, and `agy_web_search` reject an unknown `model` (and the `ANTIGRAVITY_BRIDGE_MODEL` default) with a `ToolError` listing supported models; degrades gracefully when the model list is unavailable.

## Error Handling & Troubleshooting

### Common Errors
- **"Antigravity CLI not found"**: Install CLI with `curl -fsSL https://antigravity.google/cli/install.sh | bash`
- **"Authentication required"**: Verify Antigravity authentication
- **"Timed out after X seconds"**: Increase timeout or simplify query
- **"Directory does not exist"**: Use absolute paths or verify directory
- **"Antigravity CLI produced no output" (structured `ToolError`)**: `agy --print` exited 0 with empty stdout — most often because it ran under a PTY (`FORCE_TTY=true`), which puts agy in TUI mode where it can exit without flushing the response. The default (`FORCE_TTY=false`, plain pipes) avoids this. The bridge surfaces the empty result as a real error (not a silent success); retry, or set `FORCE_TTY=false`. (Not to be confused with upstream #318, which is a *hang* on older agy/Windows.)

## Development Guidelines

- **Python 3.10+** with modern type hints (uses `from __future__ import annotations`)
- **PEP 8**, 88-char line length
- **Type hints** on all public interfaces
- **`python3`** not `python` (system python may be v2)
- **Tests**: Run `pytest` before submitting changes

## Package Information

- **Package Name**: `antigravity-bridge`
- **Entry Point**: `antigravity-bridge = "src:main"`
- **License**: Apache 2.0
- **Author**: Fojle Rabbi Rabib
- **Python**: 3.10+
- **Dependencies**: `mcp>=1.0.0`
