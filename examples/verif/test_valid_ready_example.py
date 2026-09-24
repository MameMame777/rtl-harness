"""Anatomy of a stream test (DUT: examples/bus/skid_buffer.sv).

  1. bring-up      harness_tb.lib.clkreset.bringup      clock + synchronous active-low reset
  2. driver        ValidReadySource                    offers beats, holds them until accepted
  3. sink          ValidReadySink                      drives ready, optionally with backpressure
  4. monitor       ValidReadyMonitor                   records every accepted beat
  5. scoreboard    Scoreboard                          expected sequence == observed sequence
  6. gaps          GapPolicy                           the same test, with idle cycles and stalls

The whole point of a stream test: the ACCEPTED-beat sequence must not depend on timing. Run
the scenario once continuous and once with gaps and backpressure; if only one of them fails,
the handshake is broken. Everything below the pytest entry point runs inside the simulator.
"""

from __future__ import annotations

import random
from pathlib import Path

import cocotb
from cocotb.triggers import RisingEdge

from harness_tb.lib.clkreset import bringup
from harness_tb.lib.gap import GapPolicy
from harness_tb.lib.scoreboard import Scoreboard, check
from harness_tb.lib.valid_ready import ValidReadyMonitor, ValidReadySink, ValidReadySource

WIDTH = 8
N_BEATS = 40


async def stream_scenario(dut, source_gaps: str, sink_gaps: str) -> None:
    # 1. bring-up: returns the clock handle; rst_n has been released
    clk, _ = await bringup(dut)

    # 2-4. driver on the upstream port (s_*), sink + monitor on the downstream port (m_*)
    src = ValidReadySource(dut, clk, "s")
    sink = ValidReadySink(dut, clk, "m")
    mon = ValidReadyMonitor(dut, clk, "m")
    mon.start()

    # 6. gap policies are seeded so a failure reproduces exactly
    sink.start_backpressure(GapPolicy(sink_gaps, seed=11, max_gap=3))
    source_policy = GapPolicy(source_gaps, seed=12, max_gap=3)

    # 5. the scoreboard holds the expected sequence before anything is driven
    rng = random.Random(0)
    words = [rng.getrandbits(WIDTH) for _ in range(N_BEATS)]
    sb = Scoreboard("stream")
    for w in words:
        sb.expect(w)

    await src.send_all(words, source_policy)

    # drain: wait until the monitor saw everything (bounded, so a hang becomes a failure)
    for _ in range(100):
        await RisingEdge(clk)
        if len(mon.beats) >= N_BEATS:
            break
    for b in mon.beats:
        sb.observe(b)
    sb.check()  # raises "CHECK FAILED: stream[i] ..." on the first mismatch
    check(len(mon.beats) == N_BEATS, f"no extra beats (saw {len(mon.beats)})")


@cocotb.test(timeout_time=1, timeout_unit="ms")
async def continuous(dut):
    await stream_scenario(dut, "none", "none")


@cocotb.test(timeout_time=1, timeout_unit="ms")
async def with_gaps_and_backpressure(dut):
    await stream_scenario(dut, "sparse", "adversarial")


# pytest entry point (host process): build the DUT and start the simulation. The block name
# is the file name without "test_": run_sim("valid_ready_example").
def test_valid_ready_example():
    from harness_tb.runner_support import build_and_test

    build_and_test(
        block="valid_ready_example",
        sources=["examples/bus/skid_buffer.sv"],
        toplevel="skid_buffer",
        test_dir=Path(__file__).parent,
        parameters={"WIDTH": WIDTH},
    )
