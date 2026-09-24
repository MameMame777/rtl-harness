"""Smoke test for the harness loop (lint -> sim -> CI). Not a style exemplar: see examples/.

Two-process model: pytest runs `test_smoke_counter()` (host), which builds the DUT and
launches the simulator; the @cocotb.test() coroutines run inside the Verilated executable.
Coroutine names must not start with `test_`.
"""

from __future__ import annotations

from pathlib import Path

import cocotb
from cocotb.triggers import ClockCycles, ReadOnly, RisingEdge

from harness_tb.lib.clkreset import bringup
from harness_tb.lib.scoreboard import check, check_eq

WIDTH = 4


@cocotb.test(timeout_time=100, timeout_unit="us")
async def counts_when_enabled(dut):
    clk, _ = await bringup(dut)
    dut.en.value = 0
    await ClockCycles(clk, 2)
    check_eq(int(dut.count.value), 0, "count after reset")
    dut.en.value = 1
    await ClockCycles(clk, 10)
    dut.en.value = 0
    await ClockCycles(clk, 2)
    check_eq(int(dut.count.value), 10, "count after 10 enabled cycles")


@cocotb.test(timeout_time=100, timeout_unit="us")
async def wraps_at_max(dut):
    clk, _ = await bringup(dut)
    dut.en.value = 1
    seen_wrap = False
    for _ in range((1 << WIDTH) + 2):
        await RisingEdge(clk)
        await ReadOnly()
        if int(dut.wrap.value) == 1:
            check_eq(int(dut.count.value), (1 << WIDTH) - 1, "wrap asserts at the maximum count")
            seen_wrap = True
    check(seen_wrap, "wrap was asserted once per period")


def test_smoke_counter():
    from harness_tb.runner_support import build_and_test

    build_and_test(
        block="smoke_counter",
        sources=["tb/smoke/smoke_counter.sv"],
        toplevel="smoke_counter",
        test_dir=Path(__file__).parent,
        parameters={"WIDTH": WIDTH},
    )
