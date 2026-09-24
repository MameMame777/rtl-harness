"""Build the cocotb VPI static library for Verilator on Windows (WA#5/#6).

cocotb's Verilator runner links the simulation executable with -lcocotbvpi_verilator, but the
Windows (mingw ucrt64) cocotb build does not ship that library: Verilator produces a standalone
executable and a Windows DLL cannot export VPI symbols into a host executable, so the VPI layer
must be statically linked. This module reproduces cocotb's own build: it fetches the cocotb
sdist matching the installed version (sha256-verified against rules/common/tool-versions.toml),
compiles share/lib/vpi/*.cpp into libcocotbvpi_verilator.a and drops the archive into cocotb's
libs dir -- the only -L path the runner places before -lcocotbvpi_verilator.

ensure() is idempotent: it hashes {cocotb, gcc, verilator versions, sources, flags} into a
stamp and rebuilds only when that changes. Linux: no-op.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tarfile
import tomllib
import urllib.request
from pathlib import Path

from . import site as cs

VPI_LIB_NAME = "libcocotbvpi_verilator.a"

_DEFINES = ["-DCOCOTBVPI_EXPORTS=1", "-DVERILATOR=1", "-D__STDC_FORMAT_MACROS=1", "-DWIN32=1", "-DPLI_DLLISPEC=", "-DPLI_DLLESPEC="]
_CFLAGS = ["-O2", "-std=c++17", "-fpermissive"]


def _cocotb_version() -> str:
    import importlib.metadata

    return importlib.metadata.version("cocotb")


def _libs_dir() -> Path:
    import cocotb_tools.config as cfg

    return Path(cfg.libs_dir)


def _tool_version(exe: str, *args: str) -> str:
    try:
        out = subprocess.run([exe, *(args or ("--version",))], capture_output=True, text=True, check=False)
        return (out.stdout or out.stderr).splitlines()[0].strip()
    except Exception as exc:  # noqa: BLE001 - diagnostic only
        return f"<{exe}: {exc}>"


def _pinned_sha256(version: str) -> str | None:
    tv = cs.HARNESS_ROOT / "rules" / "common" / "tool-versions.toml"
    if not tv.is_file():
        return None
    t = tomllib.loads(tv.read_text(encoding="utf-8")).get("cocotb", {})
    return t.get("sdist_sha256") if t.get("version") == version else None


def _pypi_sdist_url(version: str) -> str:
    api = f"https://pypi.org/pypi/cocotb/{version}/json"
    with urllib.request.urlopen(api, timeout=60) as resp:  # noqa: S310 - fixed https host
        data = json.load(resp)
    for u in data["urls"]:
        if u["packagetype"] == "sdist":
            return u["url"]
    raise cs.ToolchainError(f"No sdist found on PyPI for cocotb {version}.")


def _vpi_source_dir(version: str) -> Path:
    """cocotb's VPI C++ sources for *version*, fetched once into .cache and verified."""
    cache = cs.CACHE_DIR / f"cocotb-{version}-src"
    vpi_dir = cache / "src" / "cocotb" / "share" / "lib" / "vpi"
    if (vpi_dir / "VpiImpl.cpp").is_file():
        return cache / "src" / "cocotb"
    cs.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tgz = cs.CACHE_DIR / f"cocotb-{version}.tar.gz"
    if not tgz.is_file():
        url = _pypi_sdist_url(version)
        if not url.startswith("https://"):
            raise cs.ToolchainError(f"refusing non-https download: {url}")
        print(f"[bootstrap_vpi] downloading cocotb {version} sdist for the VPI sources ...")
        urllib.request.urlretrieve(url, tgz)  # noqa: S310
    want = _pinned_sha256(version)
    if want:
        got = hashlib.sha256(tgz.read_bytes()).hexdigest()
        if got != want.lower():
            tgz.unlink(missing_ok=True)
            raise cs.ToolchainError(f"cocotb sdist sha256 mismatch: expected {want}, got {got}")
    with tarfile.open(tgz) as tf:
        prefix = f"cocotb-{version}/"
        members = [m for m in tf.getmembers() if m.name.startswith(prefix) and ".." not in m.name]
        for m in members:
            m.name = m.name[len(prefix):]
        tf.extractall(cache, members=members)
    if not (vpi_dir / "VpiImpl.cpp").is_file():
        raise cs.ToolchainError(f"cocotb VPI sources not found after extracting {tgz}.")
    return cache / "src" / "cocotb"


def _stamp_inputs(version: str, sources: list[Path]) -> str:
    payload = {"cocotb": version, "gcc": _tool_version("g++"), "verilator": _tool_version("verilator_bin.exe"),
               "sources": sorted(p.name for p in sources), "defines": _DEFINES, "cflags": _CFLAGS}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def ensure(force: bool = False) -> Path | None:
    """Build (if needed) and return the path to libcocotbvpi_verilator.a. Requires the
    toolchain on PATH (call site.prepend_path first). No-op on Linux."""
    if not cs.is_windows():
        return None
    version = _cocotb_version()
    src_root = _vpi_source_dir(version)
    vpi_dir = src_root / "share" / "lib" / "vpi"
    share_inc = src_root / "share" / "include"
    sources = sorted(vpi_dir.glob("*.cpp"))
    if not sources:
        raise cs.ToolchainError(f"No VPI .cpp sources under {vpi_dir}.")

    lib_path = _libs_dir() / VPI_LIB_NAME
    stamp_path = cs.CACHE_DIR / ".vpi_stamp"
    want = _stamp_inputs(version, sources)
    if not force and lib_path.is_file() and stamp_path.is_file() and stamp_path.read_text(encoding="utf-8").strip() == want:
        return lib_path

    print(f"[bootstrap_vpi] building {VPI_LIB_NAME} (cocotb {version}) ...")
    obj_dir = cs.CACHE_DIR / "vpi_obj"
    obj_dir.mkdir(parents=True, exist_ok=True)
    includes = [f"-I{share_inc}", f"-I{src_root}", f"-I{vpi_dir}"]
    objs: list[str] = []
    for src in sources:
        obj = obj_dir / (src.stem + ".o")
        res = subprocess.run(["g++", *_CFLAGS, *_DEFINES, *includes, "-c", str(src), "-o", str(obj)], capture_output=True, text=True)
        if res.returncode != 0:
            raise cs.ToolchainError(f"VPI compile failed for {src.name}:\n{res.stderr[-4000:]}")
        objs.append(str(obj))
    if lib_path.is_file():
        lib_path.unlink()
    res = subprocess.run(["ar", "rcs", str(lib_path), *objs], capture_output=True, text=True)
    if res.returncode != 0 or not lib_path.is_file():
        raise cs.ToolchainError(f"ar failed:\n{res.stderr}")
    stamp_path.write_text(want, encoding="utf-8")
    print(f"[bootstrap_vpi] built {lib_path} ({lib_path.stat().st_size} bytes)")
    return lib_path


if __name__ == "__main__":
    cs.prepend_path()
    ensure(force="--force" in sys.argv)
    print("OK")
