"""Anatomy of a golden-model test (DUT: examples/cpu/pipelined_alu.sv).

  1. model      a plain Python function that computes what the RTL must produce
  2. stimulus   random (seeded) inputs, applied one per cycle, expectations recorded in order
  3. monitor    a coroutine that records every valid output
  4. compare    in order, after draining the pipeline

Keep the model dumb and obviously right: it is the specification. Test the latency once,
separately, so a shifted output is reported as "latency is 4, expected 3" rather than as a
data mismatch.
"""

from __future__ import annotations

import random
from pathlib import Path

import cocotb
from cocotb.triggers import RisingEdge

from harness_tb.lib.clkreset import bringup
from harness_tb.lib.scoreboard import Scoreboard, check_eq

WIDTH = 16
MASK = (1 << WIDTH) - 1
LATENCY = 3
OP_ADD, OP_SUB, OP_AND, OP_OR, OP_XOR, OP_SLL, OP_SRL, OP_SLT = range(8)


def model(op: int, a: int, b: int) -> int:  # 1. the specification
    sh = b & (WIDTH - 1)
    table = {
        OP_ADD: (a + b) & MASK,
        OP_SUB: (a - b) & MASK,
        OP_AND: a & b,
        OP_OR: a | b,
        OP_XOR: a ^ b,
        OP_SLL: (a << sh) & MASK,
        OP_SRL: a >> sh,
        OP_SLT: int(a < b),
    }
    return table[op]


@cocotb.test(timeout_time=1, timeout_unit="ms")
async def random_operations_match_the_model(dut):
    clk, _ = await bringup(dut)
    sb = Scoreboard("alu")
    observed: list[int] = []

    async def monitor():  # 3. records every valid output, in order
        while True:
            await RisingEdge(clk)
            if int(dut.out_valid.value) == 1:
                observed.append(int(dut.out_result.value))

    cocotb.start_soon(monitor())

    rng = random.Random(2024)  # 2. seeded stimulus
    for _ in range(200):
        valid = rng.random() < 0.8  # bubbles included on purpose
        op, a, b = rng.randrange(8), rng.getrandbits(WIDTH), rng.getrandbits(WIDTH)
        dut.in_valid.value = int(valid)
        dut.in_op.value = op
        dut.in_a.value = a
        dut.in_b.value = b
        if valid:
            sb.expect(model(op, a, b))
        await RisingEdge(clk)
    dut.in_valid.value = 0
    for _ in range(LATENCY + 2):  # drain
        await RisingEdge(clk)

    for o in observed:  # 4. compare in order
        sb.observe(o)
    sb.check()


@cocotb.test(timeout_time=1, timeout_unit="ms")
async def latency_is_exactly_three(dut):
    clk, _ = await bringup(dut)
    dut.in_valid.value = 1
    dut.in_op.value = OP_XOR
    dut.in_a.value = 0x0F0F
    dut.in_b.value = 0x00FF
    await RisingEdge(clk)
    dut.in_valid.value = 0
    for cycle in range(1, LATENCY + 3):
        await RisingEdge(clk)
        if int(dut.out_valid.value) == 1:
            check_eq(cycle, LATENCY, "cycles from input to out_valid")
            check_eq(int(dut.out_result.value), 0x0FF0, "xor result")
            return
    raise AssertionError("CHECK FAILED: out_valid never rose")


def test_golden_model_example():
    from harness_tb.runner_support import build_and_test

    build_and_test(
        block="golden_model_example",
        sources=["examples/cpu/pipelined_alu.sv"],
        toplevel="pipelined_alu",
        test_dir=Path(__file__).parent,
        parameters={"WIDTH": WIDTH},
    )
