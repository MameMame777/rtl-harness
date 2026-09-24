"""Exception types. Messages are user-facing and must never include secrets."""

from __future__ import annotations


class HarnessError(Exception):
    """Base class for harness failures (exit code 2 in the CLI)."""


class ConfigError(HarnessError):
    """harness.toml is missing, malformed, or incompatible with this harness version."""


class ToolMissing(HarnessError):
    """A required external tool (Verible, Verilator, the sim python, gh) was not found."""


class SafetyError(HarnessError):
    """An argument tried to reach outside the consumer project or was otherwise unsafe."""
