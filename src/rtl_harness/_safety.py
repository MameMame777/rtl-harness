"""Input validation shared by every entry point (CLI, MCP, pre-commit, CI).

The model driving the MCP server is untrusted input. Every path it hands us is resolved and
must stay inside the consumer project; block names are plain identifiers; subprocesses only
receive an allow-listed environment; output is capped.
"""

from __future__ import annotations

import fnmatch
import os
import re
from pathlib import Path

from .errors import SafetyError

MAX_OUTPUT_BYTES = 1_000_000
SOURCE_SUFFIXES = (".sv", ".svh", ".v", ".vh")

_NAME_RX = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}")

# Environment variables a child process may inherit. Everything else is dropped so a stray
# token or credential in the parent environment never reaches a tool or a test.
_ENV_ALLOW_EXACT = {
    "PATH", "PATHEXT", "COMSPEC", "SYSTEMROOT", "SystemRoot", "SYSTEMDRIVE", "SystemDrive",
    "WINDIR", "TEMP", "TMP", "TMPDIR", "HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA",
    "PROGRAMDATA", "ProgramData", "LANG", "LC_ALL", "LC_CTYPE", "TZ", "PWD", "SHELL", "TERM",
    "USERNAME", "USER", "LOGNAME", "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE",
    "PYTHONIOENCODING", "PYTHONUTF8", "PYTHONPATH", "PYTHONDONTWRITEBYTECODE",
    "MSYS2_ROOT", "VERILATOR_ROOT", "GITHUB_ACTIONS", "CI", "NO_COLOR",
}
_ENV_ALLOW_PREFIX = ("COCOTB_", "RTL_HARNESS_", "UV_", "VIRTUAL_ENV", "MSYSTEM", "GH_", "GITHUB_")


def within(root: Path, candidate: str | os.PathLike[str]) -> Path:
    """Resolve *candidate* (relative to *root* unless absolute) and require it to be inside
    *root* once symlinks are resolved. Returns the resolved absolute path."""
    root_r = Path(root).resolve()
    p = Path(candidate)
    if not p.is_absolute():
        p = root_r / p
    rp = p.resolve()
    if rp != root_r and root_r not in rp.parents:
        raise SafetyError(f"path is outside the project: {candidate}")
    return rp


def rel(root: Path, path: Path) -> str:
    """Project-relative path with forward slashes (what tools and JSON results show)."""
    return path.resolve().relative_to(Path(root).resolve()).as_posix()


def safe_glob(root: Path, patterns: list[str], exclude: list[str] | None = None,
              suffixes: tuple[str, ...] | None = SOURCE_SUFFIXES) -> list[Path]:
    """Expand glob patterns under *root* only. Symlinked files that resolve outside the
    project are skipped; excluded patterns match the project-relative posix path."""
    root_r = Path(root).resolve()
    out: dict[str, Path] = {}
    for pat in patterns:
        if Path(pat).is_absolute() or pat.startswith(("..", "/", "\\")):
            raise SafetyError(f"glob pattern must be project-relative: {pat}")
        for m in sorted(root_r.glob(pat)):
            if not m.is_file():
                continue
            try:
                rp = within(root_r, m)
            except SafetyError:
                continue
            if suffixes and rp.suffix.lower() not in suffixes:
                continue
            r = rp.relative_to(root_r).as_posix()
            if any(fnmatch.fnmatch(r, ex) for ex in exclude or []):
                continue
            out.setdefault(r, rp)
    return [out[k] for k in sorted(out)]


def check_name(name: str, what: str = "name") -> str:
    """A block / test / module name: an identifier, never a path or shell text."""
    if not isinstance(name, str) or not _NAME_RX.fullmatch(name):
        raise SafetyError(f"invalid {what}: {name!r}")
    return name


def clean_env(extra: dict[str, str] | None = None, path_prepend: str | None = None) -> dict[str, str]:
    """Allow-listed copy of the environment for child processes, plus *extra* entries."""
    env: dict[str, str] = {}
    for k, v in os.environ.items():
        if k in _ENV_ALLOW_EXACT or k.upper() in _ENV_ALLOW_EXACT or k.startswith(_ENV_ALLOW_PREFIX):
            env[k] = v
    if extra:
        env.update(extra)
    if path_prepend:
        env["PATH"] = path_prepend + os.pathsep + env.get("PATH", "")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return env


def clip(text: str, limit: int = MAX_OUTPUT_BYTES) -> tuple[str, bool]:
    """Truncate *text* to *limit* bytes; the flag says whether anything was dropped."""
    data = text.encode("utf-8", errors="replace")
    if len(data) <= limit:
        return text, False
    return data[:limit].decode("utf-8", errors="ignore") + "\n[output clipped]\n", True
