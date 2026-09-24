"""Where things are: the harness root, the consumer project root, interpreters and tools.

Nothing here is an absolute path written into the repository. Everything is derived from the
package location, the environment, or `harness.toml` found by walking up from the current
directory.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from .errors import ConfigError, ToolMissing

HARNESS_ROOT = Path(__file__).resolve().parents[2]
CONFIG_NAME = "harness.toml"
RUNTIME_DIRNAME = ".harness"


def harness_root() -> Path:
    return HARNESS_ROOT


def is_windows() -> bool:
    return os.name == "nt"


def consumer_root(start: Path | None = None) -> Path:
    """The project being worked on: RTL_HARNESS_CONSUMER, else the nearest ancestor of the
    current directory holding harness.toml, else the harness itself (self-consumption)."""
    env = os.environ.get("RTL_HARNESS_CONSUMER")
    if env:
        p = Path(env).expanduser().resolve()
        if (p / CONFIG_NAME).is_file():
            return p
        raise ConfigError(f"RTL_HARNESS_CONSUMER={env!r} has no {CONFIG_NAME}")
    cur = (start or Path.cwd()).resolve()
    for d in (cur, *cur.parents):
        if (d / CONFIG_NAME).is_file():
            return d
    if (HARNESS_ROOT / CONFIG_NAME).is_file():
        return HARNESS_ROOT
    raise ConfigError(
        f"{CONFIG_NAME} not found in {cur} or any parent. Copy templates/{CONFIG_NAME} into the "
        "project root, or set RTL_HARNESS_CONSUMER."
    )


def runtime_dir(consumer: Path) -> Path:
    d = consumer / RUNTIME_DIRNAME
    d.mkdir(parents=True, exist_ok=True)
    return d


# --- interpreters ----------------------------------------------------------------------------


def sim_python() -> Path:
    """The interpreter that runs pytest + cocotb. On Windows this must be the MSYS2 ucrt64
    python (VPI ABI), so it lives in its own venv; on Linux the project venv is fine."""
    env = os.environ.get("RTL_HARNESS_SIM_PYTHON")
    if env:
        p = Path(env)
        if p.is_file():
            return p
        raise ToolMissing(f"RTL_HARNESS_SIM_PYTHON={env!r} does not exist")
    if is_windows():
        cand = HARNESS_ROOT / ".venv-sim" / "bin" / "python.exe"
        if cand.is_file():
            return cand
        raise ToolMissing(
            ".venv-sim not found: run scripts/setup_toolchain.ps1 (creates the ucrt64 cocotb venv)"
        )
    for cand in (HARNESS_ROOT / ".venv" / "bin" / "python", Path(sys.executable)):
        if cand.is_file():
            return cand
    raise ToolMissing("no python interpreter for simulation found")


# --- tools -----------------------------------------------------------------------------------


def tools_dir() -> Path:
    env = os.environ.get("RTL_HARNESS_TOOLS")
    return Path(env).expanduser() if env else HARNESS_ROOT / ".tools"


def _exe(name: str) -> str:
    return name + (".exe" if is_windows() else "")


def find_tool(name: str, subdir: str) -> Path | None:
    """A tool from the tools dir (RTL_HARNESS_TOOLS, else <harness>/.tools) <subdir>[/bin]
    first, then PATH. Several projects can share one tools dir through the variable."""
    for cand in (tools_dir() / subdir / _exe(name), tools_dir() / subdir / "bin" / _exe(name)):
        if cand.is_file():
            return cand
    w = shutil.which(name)
    return Path(w) if w else None


def verible(tool: str) -> Path:
    p = find_tool(tool, "verible")
    if p is None:
        raise ToolMissing(f"{tool} not found: run scripts/install_verible.ps1 (or .sh)")
    return p


def gitleaks() -> Path | None:
    return find_tool("gitleaks", "gitleaks")


def msys2_root() -> Path:
    """MSYS2 install dir on Windows: MSYS2_ROOT, else derived from a verilator on PATH, else
    the standard install locations."""
    marker = ("ucrt64", "bin", "verilator_bin.exe")
    env = os.environ.get("MSYS2_ROOT")
    if env:
        p = Path(env)
        if p.joinpath(*marker).is_file():
            return p
        raise ToolMissing(f"MSYS2_ROOT={env!r} is set but ucrt64/bin/verilator_bin.exe is missing")
    for name in ("verilator_bin.exe", "verilator.bat", "verilator"):
        hit = shutil.which(name)
        if hit:
            cand = Path(hit).resolve().parents[2]
            if cand.joinpath(*marker).is_file():
                return cand
    # standard MSYS2 install roots, not user data
    candidates = [
        Path(r"C:\msys64"),  # hygiene-ok: well-known install root
        Path(r"C:\msys2"),  # hygiene-ok: well-known install root
        Path(r"C:\tools\msys64"),  # hygiene-ok: well-known install root
    ]
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidates.append(Path(local) / "msys64")
    for c in candidates:
        if c.joinpath(*marker).is_file():
            return c
    raise ToolMissing(
        "MSYS2 ucrt64 with Verilator not found. Set MSYS2_ROOT to the MSYS2 install dir "
        "(it must contain ucrt64/bin/verilator_bin.exe) or put ucrt64/bin on PATH."
    )


def verilator() -> tuple[Path, dict[str, str], str | None]:
    """(verilator executable, extra environment, PATH prefix). The real binary is called
    directly (no perl wrapper) with VERILATOR_ROOT set to a forward-slash path."""
    if is_windows():
        root = msys2_root()
        exe = root / "ucrt64" / "bin" / "verilator_bin.exe"
        env = {"VERILATOR_ROOT": (root / "ucrt64" / "share" / "verilator").as_posix()}
        prepend = os.pathsep.join([str(root / "ucrt64" / "bin"), str(root / "usr" / "bin")])
        return exe, env, prepend
    for name in ("verilator_bin", "verilator"):
        w = shutil.which(name)
        if w:
            return Path(w), {}, None
    raise ToolMissing("verilator not found on PATH")


def tool_version(exe: Path, *args: str) -> str:
    """First line of `exe --version` (never raises)."""
    from ._proc import run
    from ._safety import clean_env

    r = run([str(exe), *(args or ("--version",))], cwd=HARNESS_ROOT, env=clean_env(), timeout_s=30)
    text = (r.stdout or r.stderr).strip().splitlines()
    return text[0] if text else f"(no output, rc={r.returncode})"
