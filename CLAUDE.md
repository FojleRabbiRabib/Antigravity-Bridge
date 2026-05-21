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
uvx agy
```

**Claude Code Integration:**
```bash
# Production (recommended)
claude mcp add antigravity-bridge -s user -- uvx agy

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
├── __init__.py      # Package entry point and version
├── __main__.py      # Module execution entry point
├── config.py        # Constants and environment variable configuration
├── cli.py           # Antigravity CLI subprocess interface
├── files.py         # File attachment and preprocessing
└── tools.py         # MCP tool definitions
```

### Key Components

**`src/config.py`** — Configuration and environment variables
- All `ANTIGRAVITY_BRIDGE_*` environment variables with sensible defaults
- `get_timeout()` / `coerce_timeout()` — timeout validation
- `should_skip_permissions()` / `should_sandbox()` — flag helpers

**`src/cli.py`** — Subprocess calls to `agy`
- `execute_antigravity_simple(query, directory, timeout_seconds)` — Simple CLI bridge
- `execute_antigravity_with_files(query, directory, files_list, timeout_seconds, mode)` — File-attachment support

**`src/files.py`** — File preprocessing
- `resolve_path()` — path resolution with directory boundary checks
- `read_file_for_inline()` — read with head/tail truncation safeguards
- `prepare_inline_payload()` — build inline payload for stdin
- `prepare_at_command_prompt()` — build `@path` directives

**`src/tools.py`** — MCP tool definitions (FastMCP)
- `agy_consult()` — simple query tool
- `agy_consult_with_files()` — file context tool
- `agy_web_search()` — web search tool

### Configuration

All environment variables prefixed with `ANTIGRAVITY_BRIDGE_`:

| Variable | Default | Description |
|---|---|---|
| `ANTIGRAVITY_BRIDGE_TIMEOUT` | `120` | Global timeout override (seconds) |
| `ANTIGRAVITY_BRIDGE_DEFAULT_TIMEOUT` | `120` | Module-level default timeout |
| `ANTIGRAVITY_BRIDGE_SKIP_PERMISSIONS` | `true` | Auto-skip permissions for MCP |
| `ANTIGRAVITY_BRIDGE_SANDBOX` | `false` | Enable sandbox mode |
| `ANTIGRAVITY_BRIDGE_MAX_INLINE_FILE_COUNT` | `30` | Max files in inline mode |
| `ANTIGRAVITY_BRIDGE_MAX_INLINE_TOTAL_BYTES` | `1048576` | Max total inline payload (1MB) |
| `ANTIGRAVITY_BRIDGE_MAX_INLINE_FILE_BYTES` | `524288` | Max per-file inline size (512KB) |
| `ANTIGRAVITY_BRIDGE_INLINE_HEAD_BYTES` | `65536` | Head chunk for truncated files (64KB) |
| `ANTIGRAVITY_BRIDGE_INLINE_TAIL_BYTES` | `32768` | Tail chunk for truncated files (32KB) |

## MCP Tools Available

### `agy_consult`
- **Purpose**: Direct CLI bridge for simple queries
- **Parameters**: `query`, `directory`, `timeout_seconds`
- **Use Case**: General questions, code analysis without file attachments

### `agy_consult_with_files`
- **Purpose**: CLI bridge with file attachments for detailed analysis
- **Parameters**: `query`, `directory`, `files`, `timeout_seconds`, `mode`
- **Modes**: `"inline"` (default) or `"at_command"`
- **Use Case**: File-specific analysis, multi-file comparisons, code reviews

### `agy_web_search`
- **Purpose**: Web search queries with Antigravity CLI
- **Parameters**: `query`, `directory`, `timeout_seconds`
- **Use Case**: Current information, latest docs, recent changes

## Error Handling & Troubleshooting

### Common Errors
- **"Antigravity CLI not found"**: Install CLI with `curl -fsSL https://antigravity.google/cli/install.sh | bash`
- **"Authentication required"**: Verify Antigravity authentication
- **"Timed out after X seconds"**: Increase timeout or simplify query
- **"Directory does not exist"**: Use absolute paths or verify directory

## Development Guidelines

- **Python 3.9+** with modern type hints (uses `from __future__ import annotations` for 3.9 compat)
- **PEP 8**, 88-char line length
- **Type hints** on all public interfaces
- **`python3`** not `python` (system python may be v2)
- **Tests**: Run `pytest` before submitting changes

## Package Information

- **Package Name**: `antigravity-bridge`
- **Entry Point**: `agy = "src:main"`
- **License**: Apache 2.0
- **Author**: Fojle Rabbi Rabib
- **Python**: 3.9+
- **Dependencies**: `mcp>=1.0.0`
