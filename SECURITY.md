# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |

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

## Known Security Considerations

### Current Architecture

- **CLI Dependency**: Security depends on Antigravity CLI installation
- **File Access**: MCP tools can access files in specified directories
- **Subprocess Calls**: Uses subprocess to call `agy`
- **Network Requests**: All network requests handled by Antigravity CLI
- **Process Isolation**: Each tool call runs in an isolated subprocess

### Mitigations

- **Timeout Protection**: Configurable timeout prevents long-running attacks
- **Error Handling**: Graceful error handling without information leakage
- **No Persistent State**: Stateless operation reduces attack surface
- **Simple Architecture**: Minimal codebase reduces potential vulnerabilities

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
