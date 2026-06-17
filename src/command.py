"""Typed builder for the ``agy`` command-line invocation.

Centralising argv construction keeps the execution layer (``cli.py``) focused on
running the process, and makes option ordering/duplication easy to test.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AgyCommand:
    """A declarative description of an ``agy`` invocation."""

    query: str
    directory: str
    timeout: int
    model: str = ""
    add_dirs: tuple[str, ...] = field(default_factory=tuple)
    skip_permissions: bool = False
    sandbox: bool = False
    continue_last: bool = False
    conversation_id: str = ""
    align_print_timeout: bool = True

    def build(self) -> list[str]:
        """Return the full ``agy`` argv as a list of strings."""
        cmd: list[str] = ["agy"]

        if self.skip_permissions:
            cmd.append("--dangerously-skip-permissions")
        if self.sandbox:
            cmd.append("--sandbox")
        if self.model:
            cmd += ["--model", self.model]

        # The working directory is always added as a workspace; repeatable
        # --add-dir allows extra directories to be attached.
        cmd += ["--add-dir", self.directory]
        for extra in self.add_dirs:
            cmd += ["--add-dir", extra]

        if self.conversation_id:
            cmd += ["--conversation", self.conversation_id]
        elif self.continue_last:
            cmd.append("--continue")

        # Align agy's internal print-mode wait with our subprocess timeout so
        # agy stops gracefully instead of being SIGKILLed mid-run.
        if self.align_print_timeout:
            cmd += ["--print-timeout", f"{self.timeout}s"]

        cmd += ["--print", self.query]
        return cmd
