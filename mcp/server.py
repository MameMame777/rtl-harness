#!/usr/bin/env python3
"""rtl-harness MCP server: exactly four tools over stdio.

    run_lint      format check + Verible + Verilator + custom checks   -> summary JSON
    run_sim       build and run one cocotb block                       -> summary JSON
    get_waveform  selected signals over a time window from a VCD       (P5 stub)
    list_design   modules / params / ports / instances                 (P5 stub)

Every tool calls the same function the CLI, pre-commit and CI use (rtl_harness.*), so the
result is identical whichever entry point asked. The model is untrusted input: all paths are
confined to the consumer project by rtl_harness._safety, subprocesses never see a shell, and
tool failures come back as {"status": "error", ...} instead of crashing the server.

Start (from a consumer project; the harness is the `harness/` submodule):
    uv run --project harness --no-sync python harness/mcp/server.py
Registered by `rtl-harness sync` in .mcp.json (Claude Code) and .vscode/mcp.json (Copilot).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from mcp.server import MCPServer  # noqa: E402  (mcp>=2.2)
from rtl_harness import __version__  # noqa: E402
from rtl_harness.errors import HarnessError  # noqa: E402

INSTRUCTIONS = (
    "RTL design harness. Workflow: write or edit SystemVerilog under the project's rtl/, then "
    "call run_lint on the changed files and fix every error; then run_sim on the block's test; "
    "only when run_sim fails, call get_waveform for the signals around first_failure.sim_time. "
    "Paths are project-relative. Never add lint_off / waive comments to pass a check."
)


def _guard(fn) -> dict[str, Any]:
    try:
        return fn()
    except HarnessError as exc:
        return {"status": "error", "error": str(exc)}
    except Exception as exc:  # noqa: BLE001 - the server must keep serving
        return {"status": "error", "error": f"{type(exc).__name__}: {exc}"}


def build_server() -> MCPServer:
    mcp = MCPServer("rtl-harness", version=__version__, instructions=INSTRUCTIONS)

    @mcp.tool(
        name="run_lint",
        description=(
            "Check SystemVerilog files against the project rules: formatter (Verible), style lint "
            "(Verible), structural lint (Verilator --lint-only) and custom checks. Returns "
            "status pass|fail, the findings with file/line/rule/severity, counts, and any newly "
            "added lint suppressions. files: project-relative paths (default: all design files). "
            "fix=true rewrites files with the formatter."
        ),
    )
    def run_lint(files: list[str] | None = None, fix: bool = False) -> dict[str, Any]:
        from rtl_harness.lint import run_lint as _run_lint

        return _guard(lambda: _run_lint(files, fix=fix))

    @mcp.tool(
        name="run_sim",
        description=(
            "Build and run one cocotb block (test_<block>.py) with Verilator and return only a "
            "summary: status pass|fail|timeout|build_error, passed/failed counts, the first "
            "failure with its message and sim_time, log_path and (with waves=true) "
            "waveform_path for get_waveform. block: the name after test_ in the test file."
        ),
    )
    def run_sim(block: str, waves: bool = False, timeout_s: float = 600.0) -> dict[str, Any]:
        from rtl_harness.sim import run_sim as _run_sim

        return _guard(lambda: _run_sim(block, waves=waves, timeout_s=timeout_s))

    @mcp.tool(
        name="get_waveform",
        description=(
            "Return the value changes of the requested signals between t_start and t_end from "
            "a waveform produced by run_sim(waves=true). Ask for a few signals and a narrow "
            "window around first_failure.sim_time; clipped reports dropped changes. "
            "(Not implemented yet in this release: answers status=unimplemented.)"
        ),
    )
    def get_waveform(
        waveform_path: str,
        signals: list[str],
        t_start: int = 0,
        t_end: int | None = None,
        max_changes: int = 200,
    ) -> dict[str, Any]:
        from rtl_harness.wave import get_waveform as _get_waveform

        return _guard(lambda: _get_waveform(waveform_path, signals, t_start, t_end, max_changes))

    @mcp.tool(
        name="list_design",
        description=(
            "List the modules of the design with their parameters, ports (name, direction, "
            "width) and instances, so you can write a test or wire a block without reading "
            "every file. files: project-relative paths (default: all design files). "
            "(Not implemented yet in this release: answers status=unimplemented.)"
        ),
    )
    def list_design(files: list[str] | None = None, top: str | None = None) -> dict[str, Any]:
        from rtl_harness.design import list_design as _list_design

        return _guard(lambda: _list_design(files, top))

    return mcp


server = build_server()

if __name__ == "__main__":
    server.run(transport="stdio")
