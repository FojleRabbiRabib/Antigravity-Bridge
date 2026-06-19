"""Antigravity Bridge MCP server."""

# Defined before importing .tools so that tools.py can read src.__version__ at
# import time (the single source of truth for the advertised version).
__version__ = "1.2.1"

from .tools import main

__all__ = ["main"]
