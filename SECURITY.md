# Security Policy

## Supported Versions

| Version   | Supported          |
| --------- | ------------------ |
| 1.2.x     | :white_check_mark: |
| < 1.2     | :x: (best effort)  |

Only the latest released line receives security fixes.

## Reporting a Vulnerability

**Do NOT report security vulnerabilities through public GitHub issues.**

### How to Report

1. **GitHub Security**: Use [GitHub's private vulnerability reporting](https://github.com/FojleRabbiRabib/Antigravity-Bridge/security/advisories/new) (preferred)
2. **Private Issue**: Create a private issue if the above isn't available

### What to Include

- **Description**: Clear description of the vulnerability
- **Impact**: What could an attacker accomplish?
- **Reproduction**: Step-by-step instructions to reproduce
- **Environment**: OS, Python version, `agy --version`, Antigravity Bridge version
- **Suggested Fix**: Ideas for a solution (if any)

### Example Report

```
Vulnerability Type: [e.g., Command Injection]
Severity: [Low/Medium/High/Critical]
Affected Component: [e.g., execute_antigravity_simple function]

Description:
[Detailed description]

Steps to Reproduce:
1. [Step one]
2. [Step two]

Environment:
- OS: Ubuntu 22.04
- Python: 3.11.5
- Antigravity CLI: 1.0.0
- Antigravity Bridge: 1.0.0
```

## Response Timeline

| Severity | Initial Response | Resolution |
|----------|-----------------|------------|
| Critical | Within 24 hours | Within 1 week |
| High | Within 48 hours | Within 2 weeks |
| Medium | Within 1 week | Within 1 month |
| Low | Within 1 week | As available |

## Security Best Practices

### For Users

1. **Keep Updated**: Always use the latest version of Antigravity CLI and this bridge
2. **File Permissions**: Be careful with file paths and permissions
3. **Input Validation**: Be cautious with untrusted input in queries

### For Developers

1. **Input Sanitization**: Always validate and sanitize input
2. **Path Traversal**: Prevent directory traversal attacks
3. **Command Injection**: Avoid shell injection vulnerabilities
4. **Error Messages**: Don't leak sensitive information in errors
5. **Dependencies**: Keep `mcp` and Antigravity CLI updated

## Security Model & Controls

### Trust Boundaries

| Boundary | Trust Level | Rationale |
|----------|-------------|-----------|
| MCP client arguments | **Untrusted** | Validated before use; never interpolated into a shell |
| Host filesystem | Partially trusted | Paths are resolved and contained, not blindly followed |
| `agy` CLI + its auth | Trusted (out of scope) | The integration target; its behavior is its own threat model |
| Model responses | Forwarded verbatim | Content is passed through; no server-side filtering |

This server runs **no network code of its own** — every request is a local
`create_subprocess_exec` call to `agy` (no shell, no string interpolation).

### Controls Implemented

| Control | Where | Effect |
|---------|-------|--------|
| Path containment | `security.resolve_within_root` (symlink-aware) | Rejects escapes from the working directory in `inline` and `at_command` modes |
| Directory allowlist | `ANTIGRAVITY_BRIDGE_ALLOWED_DIRS` | Optionally locks queries to specific roots (empty = unrestricted, by design, for full-project investigation) |
| Query validation | `security.validate_query` | Length cap + control-character rejection before any subprocess call |
| Model validation | `tools._validate_model` | Rejects unknown `model` values against `agy models`; degrades gracefully if the list is unavailable |
| Strict argument checking | `ArgModelBase(extra="forbid")` | Tool schemas carry `additionalProperties: false`; unknown params raise `ToolError` server-side |
| Binary guards | `security.is_text_file` | Inline mode skips NUL-byte-detected binaries rather than dumping them |
| Attachment caps | `files.prepare_*` | File-count, per-file, and total-byte limits on inline payloads; count cap on `@`-command |
| Permission skip opt-in | `ANTIGRAVITY_BRIDGE_SKIP_PERMISSIONS` | `--dangerously-skip-permissions` is **off** by default |
| Subprocess safety | `cli._run_agy_*` | No shell, bounded timeouts, process-group teardown (no orphans), retry on transient errors only |
| Stateless | (whole server) | No session state, no persistence, no caches of secrets |

### Notes

- **No command injection**: the argv is built as a typed list (`AgyCommand`) and passed to `create_subprocess_exec`; user text is never concatenated into a shell string.
- **No secret handling**: the server holds no API keys, tokens, or credentials. The `config://settings` resource exposes only non-secret fields.
- **TOCTOU**: as with any path-checking design, a file can change between the containment check and the read; this is inherent and accepted (the agy CLI also re-resolves paths in `at_command` mode).

## Disclosure Policy

We follow responsible disclosure practices:

1. **Private Reporting**: Initial reports should be private
2. **Coordinated Timeline**: Work together on disclosure timing
3. **Credit**: Security researchers receive appropriate credit
4. **Public Disclosure**: After fix is available and deployed

## Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Python Security Guidelines](https://python.org/dev/security/)
- [GitHub Security Features](https://docs.github.com/en/code-security)
- [MCP Specification](https://modelcontextprotocol.io/)
