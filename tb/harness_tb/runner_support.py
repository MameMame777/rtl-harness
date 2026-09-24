"""build_and_test(): the one call every test_<block>.py makes from its pytest entry point.

It prepares the toolchain (Windows workarounds), builds the DUT with Verilator through
cocotb's runner, runs the cocotb tests in the Verilated executable, and prints marker lines
(RTL_HARNESS_RESULTS_XML=..., RTL_HARNESS_WAVES=..., RTL_HARNESS_BUILD_DIR=...) that
rtl_harness.sim turns into the run_sim summary.

Two-process model: pytest (host) calls this function; the @cocotb.test() coroutines in the
same file run inside the simulator's embedded Python. Coroutine names must therefore NOT start
with `test_`, or pytest would try to run them itself.
"""

from __future__ import annotations

import inspect
import os
import shutil
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

from . import site as cs

_TOOLCHAIN_READY = False


def _export_sim_dll_dirs(root: Path) -> None:
    """WA#8: tell tb/sitecustomize.py (loaded in the sim) which dirs to add_dll_directory."""
    import cocotb_tools.config as cfg

    dirs = [str(cs.ucrt64_bin(root)), str(cfg.libs_dir)]
    os.environ["COCOTB_DLL_DIRS"] = os.pathsep.join(dirs)


def _ensure_make_shim(root: Path) -> None:
    """WA#3: cocotb runs `make`; ucrt64 ships mingw32-make.exe. Provide make.exe (gitignored)."""
    cs.MAKE_SHIM_DIR.mkdir(parents=True, exist_ok=True)
    make_exe = cs.MAKE_SHIM_DIR / "make.exe"
    if not make_exe.is_file():
        shutil.copy2(cs.ucrt64_bin(root) / "mingw32-make.exe", make_exe)


def prepare_toolchain() -> None:
    """PATH + shims + static VPI lib (Windows); sys.path only (Linux). Idempotent."""
    global _TOOLCHAIN_READY
    if _TOOLCHAIN_READY:
        return
    cs.assert_sim_python()
    root = cs.prepend_path()
    if cs.is_windows() and root is not None:
        from . import bootstrap_vpi

        _ensure_make_shim(root)
        _export_sim_dll_dirs(root)
        bootstrap_vpi.ensure()
    _TOOLCHAIN_READY = True


def _resolve(src: str | os.PathLike[str], consumer: Path) -> Path:
    p = Path(src)
    return p if p.is_absolute() else (consumer / p)


def build_and_test(
    block: str,
    sources: Sequence[str | os.PathLike[str]],
    toplevel: str,
    test_dir: os.PathLike[str] | str,
    test_module: str | None = None,
    parameters: Mapping[str, object] | None = None,
    engine: str = "verilator",
    waves: bool | None = None,
    timescale: tuple[str, str] = ("1ns", "1ps"),
    testcase: str | None = None,
    build_dir: os.PathLike[str] | str | None = None,
    includes: Sequence[str | os.PathLike[str]] = (),
    defines: Mapping[str, object] | None = None,
) -> Path:
    """Build *toplevel* from *sources* (consumer-relative) and run *test_module* under *engine*.

    Raises on a build failure or any failing cocotb test (pytest reports a red). Returns the
    path to the JUnit results XML.
    """
    from cocotb_tools.runner import get_runner

    consumer = cs.consumer_root()
    test_dir = Path(test_dir).resolve()
    if test_module is None:
        test_module = Path(inspect.stack()[1].filename).stem
    if waves is None:
        waves = os.environ.get("COCOTB_WAVES") == "1"
    parameters = dict(parameters or {})
    resolved = [_resolve(s, consumer) for s in sources]
    missing = [str(p) for p in resolved if not p.is_file()]
    if missing:
        raise FileNotFoundError(f"source file(s) not found (paths are consumer-relative): {missing}")

    if engine == "verilator":
        prepare_toolchain()
        build_args = cs.common_build_args()
    elif engine == "icarus":
        cs.prepend_path()
        build_args = []
    else:
        raise cs.ToolchainError(f"Unsupported engine {engine!r} (verilator|icarus).")
    build_args += [f"-I{_resolve(i, consumer).as_posix()}" for i in includes]

    if build_dir is None:
        # Separate waves / no-waves build dirs: a --trace build leaves Vtop__Trace*.cpp behind
        # and a later no-trace rebuild in the same dir fails compiling the stale trace files.
        build_dir = cs.build_root() / (f"{block}_waves" if waves else block)
    build_dir = Path(build_dir)

    # Pin the cocotb random seed so a regression is deterministic (cocotb 2.0 randomises the
    # resume order of coroutines woken by the same trigger). Override with COCOTB_SEED.
    seed = os.environ.get("COCOTB_SEED", "1")

    runner = get_runner(engine)
    runner.build(
        sources=resolved,
        hdl_toplevel=toplevel,
        parameters=parameters,
        defines=dict(defines or {}),
        build_args=build_args,
        build_dir=build_dir,
        always=True,
        timescale=timescale,
        waves=waves,
    )
    print(f"RTL_HARNESS_BUILD_DIR={build_dir}", flush=True)
    try:
        results = runner.test(
            hdl_toplevel=toplevel,
            test_module=test_module,
            test_dir=test_dir,
            build_dir=build_dir,
            timescale=timescale,
            testcase=testcase,
            waves=waves,
            seed=seed,
            results_xml=str(build_dir / "results.xml"),  # keep the test dir clean
        )
    finally:
        # cocotb / Verilator write dump.vcd into the test dir; keep it with the build output.
        dump = test_dir / "dump.vcd"
        if waves and dump.is_file():
            target = build_dir / "dump.vcd"
            try:
                shutil.move(str(dump), str(target))
            except OSError:
                target = dump
            print(f"RTL_HARNESS_WAVES={target}", flush=True)
        for name in ("results.xml",):
            candidate = test_dir / name
            if candidate.is_file():
                print(f"RTL_HARNESS_RESULTS_XML={candidate}", flush=True)
    if isinstance(results, (str, os.PathLike)) and Path(results).is_file():
        print(f"RTL_HARNESS_RESULTS_XML={Path(results)}", flush=True)
        return Path(results)
    return test_dir / "results.xml"


def _unused() -> None:  # keep sys referenced for tooling that inspects this module
    return None if sys else None
