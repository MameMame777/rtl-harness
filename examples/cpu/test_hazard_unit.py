"""hazard_unit: forwarding priority (EX over MEM), no forwarding from x0, load-use stall.
A combinational DUT: drive inputs, wait a delta, compare with the Python model."""

from __future__ import annotations

import random
from pathlib import Path

import cocotb
from cocotb.triggers import Timer

from harness_tb.lib.scoreboard import check_eq

FWD_NONE, FWD_EX, FWD_MEM = 0, 1, 2


def model(rs1, rs2, ex_rd, ex_we, ex_load, mem_rd, mem_we):
    def sel(rs):
        if ex_we and ex_rd != 0 and ex_rd == rs:
            return FWD_EX
        if mem_we and mem_rd != 0 and mem_rd == rs:
            return FWD_MEM
        return FWD_NONE

    stall = int(ex_load and ex_rd != 0 and (ex_rd == rs1 or ex_rd == rs2))
    return sel(rs1), sel(rs2), stall


async def _apply(dut, rs1, rs2, ex_rd, ex_we, ex_load, mem_rd, mem_we):
    dut.id_rs1.value = rs1
    dut.id_rs2.value = rs2
    dut.ex_rd.value = ex_rd
    dut.ex_reg_write.value = ex_we
    dut.ex_mem_read.value = ex_load
    dut.mem_rd.value = mem_rd
    dut.mem_reg_write.value = mem_we
    await Timer(1, unit="ns")
    got = (int(dut.forward_a.value), int(dut.forward_b.value), int(dut.stall.value))
    exp = model(rs1, rs2, ex_rd, ex_we, ex_load, mem_rd, mem_we)
    check_eq(
        got, exp, f"rs1={rs1} rs2={rs2} ex_rd={ex_rd}/{ex_we}/{ex_load} mem_rd={mem_rd}/{mem_we}"
    )


@cocotb.test()
async def directed_cases(dut):
    await _apply(dut, 1, 2, 0, 0, 0, 0, 0)  # nothing in flight
    await _apply(dut, 1, 2, 1, 1, 0, 0, 0)  # EX forwards to A
    await _apply(dut, 1, 2, 2, 1, 0, 0, 0)  # EX forwards to B
    await _apply(dut, 1, 2, 0, 0, 0, 1, 1)  # MEM forwards to A
    await _apply(dut, 5, 5, 5, 1, 0, 5, 1)  # both match: EX wins
    await _apply(dut, 0, 0, 0, 1, 0, 0, 1)  # x0 is never forwarded
    await _apply(dut, 3, 4, 3, 1, 1, 0, 0)  # load-use on rs1: stall
    await _apply(dut, 3, 4, 4, 1, 1, 0, 0)  # load-use on rs2: stall
    await _apply(dut, 3, 4, 9, 1, 1, 0, 0)  # load to an unrelated register: no stall


@cocotb.test()
async def random_cases(dut):
    rng = random.Random(7)
    for _ in range(500):
        await _apply(
            dut,
            rng.randrange(8),
            rng.randrange(8),
            rng.randrange(8),
            rng.randrange(2),
            rng.randrange(2),
            rng.randrange(8),
            rng.randrange(2),
        )


def test_hazard_unit():
    from harness_tb.runner_support import build_and_test

    build_and_test(
        block="hazard_unit",
        sources=["examples/cpu/hazard_unit.sv"],
        toplevel="hazard_unit",
        test_dir=Path(__file__).parent,
        parameters={"REG_ADDR_WIDTH": 5},
    )
