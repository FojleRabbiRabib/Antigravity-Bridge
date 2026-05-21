# Contributing to Antigravity Bridge

Thank you for your interest in contributing to Antigravity Bridge! We welcome contributions from the community.

## Getting Started

### Prerequisites

- Python 3.9 or higher
- Antigravity CLI installed: `curl -fsSL https://antigravity.google/cli/install.sh | bash`
- Verify: `agy --version`
- Git for version control

### Development Setup

1. **Fork** the repository on GitHub

2. **Clone your fork**:
   ```bash
   git clone https://github.com/YOUR_USERNAME/Antigravity-Bridge.git
   cd Antigravity-Bridge
   ```

3. **Install in development mode**:
   ```bash
   pip install -e .
   ```

4. **Verify setup**:
   ```bash
   agy --version
   python3 -c "import src; print(f'v{src.__version__}')"
   ```

5. **Create a feature branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```

## Development Workflow

### Making Changes

1. Make changes in small, logical commits
2. **Test your changes**:
   ```bash
   pytest
   ```
3. Follow code style guidelines (see below)
4. Update documentation if needed

### Running Tests

```bash
# Run full test suite
pytest

# Run specific test module
pytest tests/test_cli.py -v

# Run specific test
pytest tests/test_config.py::test_get_timeout_defaults_to_120 -v
```

### Code Style Guidelines

- **Python**: Follow [PEP 8](https://pep8.org/) style guide
- **Line length**: Maximum 88 characters (Black formatter default)
- **Imports**: Group logically (standard library, third-party, local)
- **Type hints**: Include on all public function signatures
- **Docstrings**: Use clear, descriptive docstrings
- **Commands**: Use `python3` not `python` (system python may be v2)

### Example Code Style
```python
def execute_antigravity_simple(
    query: str,
    directory: str = ".",
    timeout_seconds: int | None = None,
) -> str:
    """Execute agy CLI for simple queries.

    Args:
        query: The prompt to send to Antigravity.
        directory: Working directory for the command.
        timeout_seconds: Optional per-call timeout override.

    Returns:
        CLI output or error message.
    """
    ...
```

## Types of Contributions

### Bug Fixes
- Fix existing bugs or issues
- Improve error handling
- Address edge cases

### Feature Enhancements
- Add new MCP tools (with justification)
- Improve existing tool functionality
- Add configuration options

### Documentation
- Improve README or other documentation
- Add usage examples

### Testing
- Add test cases to `tests/`
- Improve test coverage
- Add integration tests

## Pull Request Process

1. **Push to your fork**:
   ```bash
   git push origin feature/your-feature-name
   ```

2. **Create a Pull Request** with:
   - Clear title describing the change
   - Detailed description: what, why, how tested
   - Link related issues: `Fixes #123`

3. **PR Review**:
   - Automated checks will run
   - Maintainer reviews code quality, functionality, and documentation
   - Address feedback promptly

## What We Don't Accept

- Changes that add unnecessary complexity
- Features that duplicate existing functionality
- Breaking changes without strong justification and migration path
- Contributions without proper testing

## Communication Guidelines

- **Be constructive** and respectful in feedback
- **Focus on the code**, not the person
- Use [issue templates](.github/ISSUE_TEMPLATE/) for bug reports and feature requests

## Getting Help

- **GitHub Discussions**: For general questions
- **GitHub Issues**: For bug reports and feature requests
- **Documentation**: Check README.md first

## License

Contributed code is licensed under Apache 2.0. See [LICENSE](LICENSE).
