"""pipelined_alu: every operation matches a Python golden model with a latency of exactly
three cycles, with and without bubbles in the input stream."""

from __future__ import annotations

import random
from pathlib import Path

import cocotb
from cocotb.triggers import RisingEdge

from harness_tb.lib.clkreset import bringup
from harness_tb.lib.scoreboard import Scoreboard, check

WIDTH = 32
MASK = (1 << WIDTH) - 1
LATENCY = 3
OPS = {"ADD": 0, "SUB": 1, "AND": 2, "OR": 3, "XOR": 4, "SLL": 5, "SRL": 6, "SLT": 7}


def golden(op: int, a: int, b: int) -> int:
    sh = b & (WIDTH - 1)
    return {
        0: (a + b) & MASK,
        1: (a - b) & MASK,
        2: a & b,
        3: a | b,
        4: a ^ b,
        5: (a << sh) & MASK,
        6: a >> sh,
        7: int(a < b),
    }[op]


async def _drive_and_check(dut, valid_pattern) -> None:
    """valid_pattern: iterable of (valid, op, a, b) per cycle."""
    clk, _ = await bringup(dut)
    sb = Scoreboard("alu")
    outputs: list[int] = []

    async def monitor():
        while True:
            await RisingEdge(clk)
            if int(dut.out_valid.value) == 1:
                outputs.append(int(dut.out_result.value))
                zero = int(dut.out_zero.value)
                check(zero == (int(dut.out_result.value) == 0), "out_zero tracks out_result")

    cocotb.start_soon(monitor())
    for valid, op, a, b in valid_pattern:
        dut.in_valid.value = valid
        dut.in_op.value = op
        dut.in_a.value = a
        dut.in_b.value = b
        if valid:
            sb.expect(golden(op, a, b))
        await RisingEdge(clk)
    dut.in_valid.value = 0
    for _ in range(LATENCY + 2):
        await RisingEdge(clk)
    for o in outputs:
        sb.observe(o)
    sb.check()


@cocotb.test(timeout_time=1, timeout_unit="ms")
async def every_op_directed(dut):
    pattern = []
    for name, op in OPS.items():
        for a, b in ((0, 0), (1, 1), (MASK, 1), (0x8000_0000, 4), (7, 3), (3, 7)):
            pattern.append((1, op, a, b))
    await _drive_and_check(dut, pattern)


@cocotb.test(timeout_time=1, timeout_unit="ms")
async def random_with_bubbles(dut):
    rng = random.Random(1)
    pattern = [
        (rng.random() < 0.7, rng.randrange(8), rng.getrandbits(WIDTH), rng.getrandbits(WIDTH))
        for _ in range(300)
    ]
    await _drive_and_check(dut, [(int(v), op, a, b) for v, op, a, b in pattern])


@cocotb.test(timeout_time=1, timeout_unit="ms")
async def latency_is_three(dut):
    clk, _ = await bringup(dut)
    dut.in_valid.value = 1
    dut.in_op.value = OPS["ADD"]
    dut.in_a.value = 40
    dut.in_b.value = 2
    await RisingEdge(clk)
    dut.in_valid.value = 0
    seen_at = None
    for cycle in range(1, LATENCY + 3):
        await RisingEdge(clk)
        if int(dut.out_valid.value) == 1:
            seen_at = cycle
            check(int(dut.out_result.value) == 42, "result of 40 + 2")
            break
    check(seen_at == LATENCY, f"out_valid after {seen_at} cycles, expected {LATENCY}")


def test_pipelined_alu():
    from harness_tb.runner_support import build_and_test

    build_and_test(
        block="pipelined_alu",
        sources=["examples/cpu/pipelined_alu.sv"],
        toplevel="pipelined_alu",
        test_dir=Path(__file__).parent,
        parameters={"WIDTH": WIDTH},
    )
