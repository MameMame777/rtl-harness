"""Toolchain and path resolution for the cocotb + Verilator harness.

Native Windows (MSYS2 ucrt64, no WSL) needs a handful of workarounds (WA#1..#8, see
tb/README.md). This module owns the path-related ones and is a no-op on Linux, where the
container / distribution provides verilator and cocotb ships its VPI libraries.

MSYS2 root resolution order (Windows):
  1. $MSYS2_ROOT
  2. derived from a verilator(.bat|_bin.exe) found on PATH
  3. well-known install roots
No absolute path is committed anywhere; everything derives from the resolved root.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

TB_DIR = Path(__file__).resolve().parents[1]  # <harness>/tb
HARNESS_ROOT = TB_DIR.parent
TOOLCHAIN_DIR = TB_DIR / "toolchain"
MAKE_SHIM_DIR = TOOLCHAIN_DIR / "make_shim"
CACHE_DIR = HARNESS_ROOT / ".cache"  # VPI sources / objects / stamp (gitignored)
VPI_LIB_NAME = "libcocotbvpi_verilator.a"

# standard MSYS2 install roots, not user data
_WELL_KNOWN_ROOTS = (
    r"C:\msys64",  # hygiene-ok: well-known install root
    r"C:\msys2",  # hygiene-ok: well-known install root
    r"C:\tools\msys64",  # hygiene-ok: well-known install root
)


class ToolchainError(RuntimeError):
    """The toolchain cannot be located or is incomplete."""


def is_windows() -> bool:
    return os.name == "nt"


# --- consumer project ------------------------------------------------------------------------


def consumer_root() -> Path:
    """RTL_HARNESS_CONSUMER, else the nearest ancestor of cwd with harness.toml, else the
    harness itself. Mirrors rtl_harness.paths.consumer_root without importing that package
    (the sim interpreter only has this one)."""
    env = os.environ.get("RTL_HARNESS_CONSUMER")
    if env:
        return Path(env).resolve()
    cur = Path.cwd().resolve()
    for d in (cur, *cur.parents):
        if (d / "harness.toml").is_file():
            return d
    return HARNESS_ROOT


def build_root() -> Path:
    env = os.environ.get("RTL_HARNESS_BUILD_DIR")
    return Path(env).resolve() if env else consumer_root() / ".harness" / "build"


# --- MSYS2 (Windows only) ----------------------------------------------------------------------


def _is_valid_root(p: Path | None) -> bool:
    return p is not None and (p / "ucrt64" / "bin" / "verilator_bin.exe").is_file()


def _root_from_path_verilator() -> Path | None:
    for name in ("verilator_bin.exe", "verilator.bat", "verilator"):
        hit = shutil.which(name)
        if hit:
            cand = Path(hit).resolve().parents[2]
            if _is_valid_root(cand):
                return cand
    return None


def msys2_root() -> Path:
    env = os.environ.get("MSYS2_ROOT")
    if env:
        p = Path(env)
        if _is_valid_root(p):
            return p
        raise ToolchainError(
            f"MSYS2_ROOT={env!r} is set but ucrt64/bin/verilator_bin.exe is missing."
        )
    derived = _root_from_path_verilator()
    if derived:
        return derived
    candidates = list(_WELL_KNOWN_ROOTS)
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidates.append(str(Path(local) / "msys64"))
    for c in candidates:
        if _is_valid_root(Path(c)):
            return Path(c)
    raise ToolchainError(
        "MSYS2 ucrt64 toolchain not found. Set MSYS2_ROOT to the install dir (it must contain "
        "ucrt64/bin/verilator_bin.exe) or put the ucrt64 bin dir on PATH."
    )


def ucrt64_bin(root: Path | None = None) -> Path:
    return (root or msys2_root()) / "ucrt64" / "bin"


def usr_bin(root: Path | None = None) -> Path:
    return (root or msys2_root()) / "usr" / "bin"


def verilator_root(root: Path | None = None) -> str:
    # WA#4: forward slashes, else the path is mangled inside the generated Makefiles.
    return ((root or msys2_root()) / "ucrt64" / "share" / "verilator").as_posix()


def assert_sim_python() -> None:
    """On Windows the VPI link is ABI-tied to the MinGW ucrt64 interpreter: refuse anything
    else early, with an actionable message (WA: MSVC python silently mismatches)."""
    if not is_windows():
        return
    root = msys2_root()
    exe = Path(sys.executable).resolve()
    base = Path(sys.base_prefix).resolve()
    ucrt = (root / "ucrt64").resolve()
    if not ((ucrt in exe.parents) or (base == ucrt) or (ucrt in base.parents)):
        raise ToolchainError(
            "cocotb tests must run under the MSYS2 ucrt64 python (or a venv based on it).\n"
            f"  running:     {exe}\n  base_prefix: {base}\n  expected:    {ucrt}\n"
            "Use `rtl-harness sim <block>` (it selects <harness>/.venv-sim) or scripts/run.ps1."
        )


# --- environment for cocotb's runner ------------------------------------------------------------


def prepend_path(root: Path | None = None) -> Path | None:
    """Make the toolchain discoverable to cocotb's runner (idempotent within a process).

    Windows: prepends the perl `verilator` wrapper (WA#2), the make.exe shim (WA#3),
    ucrt64/bin (gcc, verilator_bin, python) and usr/bin (perl) (WA#1); exports VERILATOR_ROOT
    (WA#4). Also puts tb/ on sys.path so cocotb propagates it (via PYTHONPATH) to the embedded
    interpreter, which needs tb/sitecustomize.py (WA#8) and harness_tb.lib.
    Linux: only the sys.path part.
    """
    if str(TB_DIR) not in sys.path:
        sys.path.insert(0, str(TB_DIR))
    if not is_windows():
        return None
    root = root or msys2_root()
    parts = [str(TOOLCHAIN_DIR), str(MAKE_SHIM_DIR), str(ucrt64_bin(root)), str(usr_bin(root))]
    existing = os.environ.get("PATH", "")
    if not existing.startswith(parts[0]):
        os.environ["PATH"] = os.pathsep.join(parts) + (os.pathsep + existing if existing else "")
    os.environ["VERILATOR_ROOT"] = verilator_root(root)
    return root


def common_build_args() -> list[str]:
    """Verilator build_args shared by every block.

    Windows (WA#5/#6): force -O2 (ucrt64's libstdc++ lacks the out-of-line std::string move
    ctor that -Os references), link -lgpi/-lgpilog for the statically linked VPI lib, and
    silence g++'s dllimport redeclaration noise. -Wno-fatal keeps Verilator's lint warnings
    visible but non-fatal for the BUILD: the lint verdict comes from run_lint, not from here.
    """
    if is_windows():
        return [
            "-Wno-fatal",
            "-CFLAGS",
            "-O2",
            "-CFLAGS",
            "-Wno-attributes",
            "-LDFLAGS",
            "-lgpi",
            "-LDFLAGS",
            "-lgpilog",
        ]
    return ["-Wno-fatal"]


def summary() -> str:
    lines = [
        f"harness root  : {HARNESS_ROOT}",
        f"consumer root : {consumer_root()}",
        f"build root    : {build_root()}",
    ]
    if is_windows():
        root = msys2_root()
        lines += [f"MSYS2_ROOT    : {root}", f"VERILATOR_ROOT: {verilator_root(root)}"]
    return "\n".join(lines)


if __name__ == "__main__":
    print(summary())
