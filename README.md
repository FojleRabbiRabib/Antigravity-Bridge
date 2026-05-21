# Antigravity Bridge

![CI Status](https://github.com/FojleRabbiRabib/Antigravity-Bridge/actions/workflows/ci.yml/badge.svg)
![PyPI Version](https://img.shields.io/pypi/v/antigravity-bridge)
![Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-blue.svg)
![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)
![MCP Compatible](https://img.shields.io/badge/MCP-compatible-green.svg)

A lightweight MCP (Model Context Protocol) server that enables AI coding assistants to interact with Antigravity AI through the official CLI. Zero API costs, stateless architecture, minimal dependencies. Production-ready with comprehensive CI/CD automation.

## Features

- **Direct Antigravity CLI Integration**: Zero API costs using the official `agy` CLI
- **Three MCP Tools**: Basic queries, file analysis, and web search capabilities
- **Stateless Operation**: No sessions, caching, or complex state management
- **Production Ready**: Robust error handling with configurable timeouts
- **Minimal Dependencies**: Only requires `mcp>=1.0.0` and Antigravity CLI
- **Easy Deployment**: Support for both `uvx` and traditional `pip` installation
- **Universal MCP Compatibility**: Works with Claude Code, Cursor, VS Code, Windsurf, Cline, Void, Cherry Studio, Augment, Roo Code, Zencoder, and any MCP-compatible client
- **Modern Python**: Python 3.10+ with type hints and pathlib

## Prerequisites

Install the Antigravity CLI:

```bash
# macOS / Linux
curl -fsSL https://antigravity.google/cli/install.sh | bash

# Windows PowerShell
irm https://antigravity.google/cli/install.ps1 | iex

# Verify installation
agy --version
```

Authentication is handled internally by Antigravity — no separate login command needed.

## Installation

**Recommended: PyPI with uvx**
```bash
claude mcp add antigravity-bridge -s user -- uvx agy
```

**From PyPI**
```bash
pip install antigravity-bridge
claude mcp add antigravity-bridge -s user -- uvx agy
```

**From Source**
```bash
git clone https://github.com/FojleRabbiRabib/Antigravity-Bridge.git
cd antigravity-bridge
pip install -e .

# Development mode
claude mcp add antigravity-bridge-dev -s user -- python3 -m src
```

## Configuration

### Environment Variables

All configuration is done through environment variables prefixed with `ANTIGRAVITY_BRIDGE_`:

| Variable | Default | Description |
|---|---|---|
| `ANTIGRAVITY_BRIDGE_TIMEOUT` | `120` | Global timeout override (seconds) |
| `ANTIGRAVITY_BRIDGE_DEFAULT_TIMEOUT` | `120` | Module-level default timeout |
| `ANTIGRAVITY_BRIDGE_SKIP_PERMISSIONS` | `true` | Add `--dangerously-skip-permissions` for MCP automation |
| `ANTIGRAVITY_BRIDGE_SANDBOX` | `false` | Add `--sandbox` for restricted execution |
| `ANTIGRAVITY_BRIDGE_MAX_INLINE_FILE_COUNT` | `30` | Max files in inline mode |
| `ANTIGRAVITY_BRIDGE_MAX_INLINE_TOTAL_BYTES` | `1048576` (1MB) | Max total inline payload |
| `ANTIGRAVITY_BRIDGE_MAX_INLINE_FILE_BYTES` | `524288` (512KB) | Max per-file inline size |
| `ANTIGRAVITY_BRIDGE_INLINE_HEAD_BYTES` | `65536` (64KB) | Head chunk for truncated files |
| `ANTIGRAVITY_BRIDGE_INLINE_TAIL_BYTES` | `32768` (32KB) | Tail chunk for truncated files |

**Timeout example:**
```bash
claude mcp add antigravity-bridge -s user --env ANTIGRAVITY_BRIDGE_TIMEOUT=180 -- uvx agy
```

## Available Tools

### `agy_consult`
Direct CLI bridge for simple queries.

**Parameters:**
- `query` (string, required): The question or prompt to send to Antigravity
- `directory` (string, required): Working directory for the query
- `timeout_seconds` (int, optional): Override execution timeout for this request

**Example:**
```python
agy_consult(query="What authentication patterns are used?", directory="/path/to/project")
```

### `agy_consult_with_files`
CLI bridge with file attachments for detailed analysis.

**Parameters:**
- `query` (string, required): The question or prompt
- `directory` (string, required): Working directory
- `files` (list, required): List of file paths relative to the directory
- `timeout_seconds` (int, optional): Override execution timeout
- `mode` (string, optional): `"inline"` (default) or `"at_command"`

**File Modes:**
- `inline` — streams truncated file snippets directly in the prompt
- `at_command` — emits `@path` directives so Antigravity CLI resolves files itself

**Example:**
```python
agy_consult_with_files(
    query="Review these auth files for security issues",
    directory="/path/to/project",
    files=["src/auth.py", "src/middleware.py"],
    mode="at_command"
)
```

### `agy_web_search`
Queries with web search context. Best-effort — the model decides when to search.

**Parameters:**
- `query` (string, required): Search query or question
- `directory` (string, required): Working directory for command execution
- `timeout_seconds` (int, optional): Override execution timeout

**Example:**
```python
agy_web_search(query="latest Python 3.13 features")
```

## Multi-Client Support

Antigravity Bridge works with any MCP-compatible AI coding assistant. The server implementation is identical across clients — only the configuration differs.

### Claude Code
```bash
claude mcp add antigravity-bridge -s user -- uvx agy
```

### Cursor
**Global** (`~/.cursor/mcp.json`):
```json
{
  "mcpServers": {
    "antigravity-bridge": {
      "command": "uvx",
      "args": ["agy"]
    }
  }
}
```

### VS Code
**Configuration** (`.vscode/mcp.json`):
```json
{
  "servers": {
    "antigravity-bridge": {
      "type": "stdio",
      "command": "uvx",
      "args": ["agy"]
    }
  }
}
```

### Windsurf
```json
{
  "mcpServers": {
    "antigravity-bridge": {
      "command": "uvx",
      "args": ["agy"]
    }
  }
}
```

### Cline (VS Code Extension)
1. Click **MCP Servers** in top navigation
2. Select **Installed** tab → **Advanced MCP Settings**
3. Add to `cline_mcp_settings.json`:
```json
{
  "mcpServers": {
    "antigravity-bridge": {
      "command": "uvx",
      "args": ["agy"]
    }
  }
}
```

### Void
`Settings` → `MCP` → `Add MCP Server`
```json
{
  "command": "uvx",
  "args": ["agy"]
}
```

### Cherry Studio
`Settings` → `MCP Servers` → `Add Server`
- Name: `antigravity-bridge`
- Type: `STDIO`
- Command: `uvx`
- Arguments: `["agy"]`

### Augment
Click hamburger menu → `Settings` → `Tools` → `+ Add MCP`
- Command: `uvx agy`
- Name: Antigravity Bridge

### Roo Code
`Settings` → `MCP Servers` → `Edit Global Config`
```json
{
  "mcpServers": {
    "antigravity-bridge": {
      "command": "uvx",
      "args": ["agy"]
    }
  }
}
```

### Zencoder
Zencoder menu → `Tools` → `Add Custom MCP`
```json
{
  "command": "uvx",
  "args": ["agy"]
}
```

## Architecture

### Design Principles
- **CLI-First**: Direct subprocess calls to `agy --print`
- **Stateless**: Each tool call is independent with no session state
- **Adaptive Timeout**: Defaults to 120 seconds, overridable per request or via env var
- **Attachment Guardrails**: Inline mode enforces byte/quantity caps; `@` mode delegates to Antigravity CLI
- **Fail-Fast**: Clear error messages with simple error handling
- **Zero Extra Dependencies**: Only `mcp>=1.0.0` beyond the Antigravity CLI

### Module Structure
```
src/
├── __init__.py      # Package entry point, version
├── __main__.py      # Module execution entry point
├── config.py        # Constants and environment variable configuration
├── cli.py           # Subprocess calls to agy
├── files.py         # File handling (inline, @-command, truncation)
└── tools.py         # MCP tool definitions (FastMCP)
```

### File Handling Safeguards
- Inline transfers cap at 512KB per file and 1MB per request
- Oversized files are truncated to head/tail snippets with warnings
- Tune caps via `ANTIGRAVITY_BRIDGE_MAX_INLINE_*` env vars
- Use `mode="at_command"` for larger payloads

## Development

```bash
# Install in development mode
pip install -e .

# Run tests
pytest

# Run MCP server directly
python3 -m src

# Verify CLI availability
agy --version
```

### Build & Distribution
```bash
# Clean build
rm -rf dist/ build/ *.egg-info

# Build package
uvx --from build pyproject-build

# Verify build
pip install dist/*.whl
python3 -c "import src; print(f'v{src.__version__}')"
```

## Troubleshooting

| Error | Solution |
|---|---|
| "Antigravity CLI not found" | `curl -fsSL https://antigravity.google/cli/install.sh \| bash` |
| "Authentication required" | Verify Antigravity authentication |
| "Timed out after X seconds" | Increase timeout or simplify query |
| "Directory does not exist" | Use absolute paths or verify directory |
| "No files provided" | Provide at least one valid file path |
| "Unsupported files mode" | Use `"inline"` or `"at_command"` |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines.

## License

Apache 2.0 — see [LICENSE](LICENSE).

## Support

- **Issues**: [GitHub Issues](https://github.com/FojleRabbiRabib/Antigravity-Bridge/issues)
- **Discussions**: [GitHub Discussions](https://github.com/FojleRabbiRabib/Antigravity-Bridge/discussions)
