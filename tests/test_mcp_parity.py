"""The MCP server exposes exactly four tools and returns the same JSON as the CLI functions."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
from pathlib import Path

import pytest

pytest.importorskip("mcp")
from mcp.client import Client  # noqa: E402

from rtl_harness import lint  # noqa: E402
from rtl_harness.config import load_config  # noqa: E402
from tests.conftest import HARNESS, requires_sim, requires_verible, requires_verilator  # noqa: E402

GOOD = (HARNESS / "tb" / "smoke" / "smoke_counter.sv").read_text(encoding="utf-8")


def _server():
    spec = importlib.util.spec_from_file_location(
        "rtl_harness_mcp_server", HARNESS / "mcp" / "server.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.server


def _payload(result) -> dict:
    for attr in ("structuredContent", "structured_content"):
        sc = getattr(result, attr, None)
        if sc:
            return sc
    text = "".join(getattr(c, "text", "") for c in result.content)
    return json.loads(text)


def call(name: str, args: dict) -> dict:
    async def go():
        async with Client(_server()) as c:
            return _payload(await c.call_tool(name, args))

    return asyncio.run(go())


def test_exactly_four_tools():
    async def go():
        async with Client(_server()) as c:
            return sorted(t.name for t in (await c.list_tools()).tools)

    assert asyncio.run(go()) == ["get_waveform", "list_design", "run_lint", "run_sim"]


@requires_verible
@requires_verilator
def test_run_lint_parity(consumer: Path):
    (consumer / "rtl" / "smoke_counter.sv").write_text(GOOD, encoding="utf-8", newline="\n")
    via_mcp = call("run_lint", {"files": ["rtl/smoke_counter.sv"]})
    via_cli = lint.run_lint(["rtl/smoke_counter.sv"], cfg=load_config(consumer))
    for r in (via_mcp, via_cli):
        r["source"].pop("duration_s", None)
    assert via_mcp == via_cli
    assert via_mcp["status"] == "pass"


def test_outside_path_is_an_error_not_a_crash(consumer: Path):
    r = call("run_lint", {"files": ["../outside.sv"]})
    assert r["status"] == "error" and "outside" in r["error"]
    r = call("get_waveform", {"waveform_path": "../x.vcd", "signals": ["a"]})
    assert r["status"] == "error"
    r = call("run_sim", {"block": "no_such_block"})
    assert r["status"] == "error" and "unknown block" in r["error"]


def test_stubs_answer_with_the_contract_keys(consumer: Path):
    r = call("list_design", {})
    assert r["status"] == "unimplemented" and set(r) >= {"top", "modules", "source"}
    (consumer / ".harness").mkdir(exist_ok=True)
    (consumer / ".harness" / "dump.vcd").write_text("", encoding="utf-8")
    r = call(
        "get_waveform", {"waveform_path": ".harness/dump.vcd", "signals": ["top.a"], "t_start": 0}
    )
    assert r["status"] == "unimplemented" and set(r) >= {
        "signals",
        "clipped",
        "time_unit",
        "missing",
        "source",
    }


@requires_sim
def test_run_sim_parity(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("RTL_HARNESS_CONSUMER", str(HARNESS))
    r = call("run_sim", {"block": "smoke_counter"})
    assert r["status"] == "pass" and r["failed"] == 0 and r["first_failure"] is None
    assert set(r) >= {
        "status",
        "passed",
        "failed",
        "first_failure",
        "log_path",
        "waveform_path",
        "duration_s",
        "source",
    }


def test_stdio_handshake_lists_tools(monkeypatch: pytest.MonkeyPatch):
    """The real transport: spawn the server the way .mcp.json does and list its tools."""
    from mcp.client.stdio import StdioServerParameters

    monkeypatch.chdir(HARNESS)
    env = {k: v for k, v in os.environ.items()}
    params = StdioServerParameters(
        command="uv",
        args=["run", "--project", ".", "--no-sync", "python", "mcp/server.py"],
        env=env,
        cwd=str(HARNESS),
    )

    async def go():
        async with Client(params, read_timeout_seconds=60) as c:
            return sorted(t.name for t in (await c.list_tools()).tools)

    assert asyncio.run(go()) == ["get_waveform", "list_design", "run_lint", "run_sim"]
