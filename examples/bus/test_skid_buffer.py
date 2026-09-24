"""skid_buffer: order and count are preserved under random gaps and backpressure, and the
buffer sustains one beat per cycle when the sink is always ready."""

from __future__ import annotations

import random
from pathlib import Path

import cocotb
from cocotb.triggers import ClockCycles, RisingEdge

from harness_tb.lib.clkreset import bringup
from harness_tb.lib.gap import GapPolicy
from harness_tb.lib.scoreboard import Scoreboard, check
from harness_tb.lib.valid_ready import ValidReadyMonitor, ValidReadySink, ValidReadySource

WIDTH = 16
N_BEATS = 64


async def _run_stream(dut, source_gaps: str, sink_gaps: str) -> Scoreboard:
    clk, _ = await bringup(dut)
    src = ValidReadySource(dut, clk, "s")
    sink = ValidReadySink(dut, clk, "m")
    mon = ValidReadyMonitor(dut, clk, "m")
    mon.start()
    sink.start_backpressure(GapPolicy(sink_gaps, seed=2, max_gap=4))
    rng = random.Random(1)
    sb = Scoreboard("skid_buffer")
    words = [rng.getrandbits(WIDTH) for _ in range(N_BEATS)]
    for w in words:
        sb.expect(w)
    await src.send_all(words, GapPolicy(source_gaps, seed=3, max_gap=3))
    for _ in range(200):
        await RisingEdge(clk)
        if len(mon.beats) >= N_BEATS:
            break
    for b in mon.beats:
        sb.observe(b)
    sb.check()
    return sb


@cocotb.test(timeout_time=1, timeout_unit="ms")
async def continuous_stream(dut):
    await _run_stream(dut, "none", "none")


@cocotb.test(timeout_time=1, timeout_unit="ms")
async def gaps_and_backpressure(dut):
    await _run_stream(dut, "adversarial", "burst")


@cocotb.test(timeout_time=1, timeout_unit="ms")
async def full_throughput_when_sink_ready(dut):
    clk, _ = await bringup(dut)
    src = ValidReadySource(dut, clk, "s")
    ValidReadySink(dut, clk, "m", ready=True)
    mon = ValidReadyMonitor(dut, clk, "m")
    mon.start()
    words = list(range(N_BEATS))
    task = cocotb.start_soon(src.send_all(words, GapPolicy("none")))
    cycles = 0
    while len(mon.beats) < N_BEATS:
        await RisingEdge(clk)
        cycles += 1
        check(
            cycles < N_BEATS + 8,
            f"stream stalled: {len(mon.beats)} of {N_BEATS} beats after {cycles} cycles",
        )
    await task
    # N beats need N cycles plus the two-stage pipeline latency
    check(
        cycles <= N_BEATS + 4,
        f"throughput below one beat per cycle: {cycles} cycles for {N_BEATS} beats",
    )
    await ClockCycles(clk, 2)
    check(int(dut.m_valid.value) == 0, "m_valid drops after the last beat")


def test_skid_buffer():
    from harness_tb.runner_support import build_and_test

    build_and_test(
        block="skid_buffer",
        sources=["examples/bus/skid_buffer.sv"],
        toplevel="skid_buffer",
        test_dir=Path(__file__).parent,
        parameters={"WIDTH": WIDTH},
    )
