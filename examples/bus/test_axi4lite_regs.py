"""axi4lite_regs: read/write registers, byte strobes, SLVERR for out-of-range or unaligned
addresses, and address/data beats arriving together or in either order.

Protocol helpers live in the test (axil_write / axil_read): they sample right after the rising
edge, deassert a beat once it was accepted, and never re-offer it.
"""

from __future__ import annotations

from pathlib import Path

import cocotb
from cocotb.triggers import ClockCycles, RisingEdge

from harness_tb.lib.clkreset import bringup
from harness_tb.lib.scoreboard import check, check_eq

ADDR_WIDTH = 8
DATA_WIDTH = 32
NUM_REGS = 4
RESP_OKAY = 0b00
RESP_SLVERR = 0b10
MASK = (1 << DATA_WIDTH) - 1


async def axil_write(
    dut, clk, addr: int, data: int, strb: int = 0xF, order: str = "together"
) -> int:
    """One AXI4-Lite write; returns bresp. order: together | data_first | addr_first."""
    aw_done = w_done = False
    dut.s_axil_bready.value = 1

    def offer_aw():
        dut.s_axil_awaddr.value = addr
        dut.s_axil_awvalid.value = 1

    def offer_w():
        dut.s_axil_wdata.value = data
        dut.s_axil_wstrb.value = strb
        dut.s_axil_wvalid.value = 1

    if order == "data_first":
        offer_w()
    elif order == "addr_first":
        offer_aw()
    else:
        offer_aw()
        offer_w()
    resp = None
    for cycle in range(40):
        await RisingEdge(clk)
        # a beat offered before this edge is accepted when its ready was high at the edge
        if (
            not aw_done
            and int(dut.s_axil_awvalid.value) == 1
            and int(dut.s_axil_awready.value) == 1
        ):
            aw_done = True
            dut.s_axil_awvalid.value = 0
        if not w_done and int(dut.s_axil_wvalid.value) == 1 and int(dut.s_axil_wready.value) == 1:
            w_done = True
            dut.s_axil_wvalid.value = 0
        if cycle == 0 and order == "data_first":
            offer_aw()
        if cycle == 0 and order == "addr_first":
            offer_w()
        if int(dut.s_axil_bvalid.value) == 1:
            resp = int(dut.s_axil_bresp.value)
            break
    dut.s_axil_bready.value = 0
    check(
        aw_done and w_done and resp is not None,
        f"write completed (aw={aw_done} w={w_done} bresp={resp})",
    )
    return resp


async def axil_read(dut, clk, addr: int) -> tuple[int, int]:
    """One AXI4-Lite read; returns (rdata, rresp)."""
    dut.s_axil_araddr.value = addr
    dut.s_axil_arvalid.value = 1
    dut.s_axil_rready.value = 1
    ar_done = False
    for _ in range(40):
        await RisingEdge(clk)
        if not ar_done and int(dut.s_axil_arready.value) == 1:
            ar_done = True
            dut.s_axil_arvalid.value = 0
        if int(dut.s_axil_rvalid.value) == 1:
            dut.s_axil_rready.value = 0
            return int(dut.s_axil_rdata.value), int(dut.s_axil_rresp.value)
    raise AssertionError("CHECK FAILED: no read response")


async def _setup(dut):
    for name in (
        "s_axil_awvalid",
        "s_axil_wvalid",
        "s_axil_bready",
        "s_axil_arvalid",
        "s_axil_rready",
    ):
        getattr(dut, name).value = 0
    clk, _ = await bringup(dut)
    return clk


@cocotb.test(timeout_time=1, timeout_unit="ms")
async def write_then_read_all_registers(dut):
    clk = await _setup(dut)
    values = [(0x1000_0000 * (i + 1) + i) & MASK for i in range(NUM_REGS)]
    for i, v in enumerate(values):
        check_eq(await axil_write(dut, clk, i * 4, v), RESP_OKAY, f"bresp reg {i}")
    for i, v in enumerate(values):
        check_eq(await axil_read(dut, clk, i * 4), (v, RESP_OKAY), f"read back reg {i}")
    reg_out = int(
        dut.reg_out.value
    )  # packed [NUM_REGS-1:0][DATA_WIDTH-1:0]: register i is bits [32i +: 32]
    for i, v in enumerate(values):
        check_eq((reg_out >> (DATA_WIDTH * i)) & MASK, v, f"reg_out[{i}]")


@cocotb.test(timeout_time=1, timeout_unit="ms")
async def beat_order_and_byte_strobes(dut):
    clk = await _setup(dut)
    check_eq(
        await axil_write(dut, clk, 4, 0xAABBCCDD, order="addr_first"),
        RESP_OKAY,
        "address before data",
    )
    check_eq(await axil_read(dut, clk, 4), (0xAABBCCDD, RESP_OKAY), "full write")
    check_eq(
        await axil_write(dut, clk, 4, 0x11223344, strb=0b0101, order="data_first"),
        RESP_OKAY,
        "data before address",
    )
    check_eq(
        await axil_read(dut, clk, 4), (0xAA22CC44, RESP_OKAY), "only the strobed bytes changed"
    )


@cocotb.test(timeout_time=1, timeout_unit="ms")
async def bad_addresses_answer_slverr(dut):
    clk = await _setup(dut)
    check_eq(
        await axil_write(dut, clk, NUM_REGS * 4, 0xDEADBEEF),
        RESP_SLVERR,
        "write beyond the last register",
    )
    check_eq(await axil_write(dut, clk, 2, 0xDEADBEEF), RESP_SLVERR, "unaligned write")
    check_eq(
        await axil_read(dut, clk, NUM_REGS * 4), (0, RESP_SLVERR), "read beyond the last register"
    )
    _, resp = await axil_read(dut, clk, 0)
    check_eq(resp, RESP_OKAY, "the slave keeps working afterwards")
    await ClockCycles(clk, 2)


def test_axi4lite_regs():
    from harness_tb.runner_support import build_and_test

    build_and_test(
        block="axi4lite_regs",
        sources=["examples/bus/axi4lite_regs.sv"],
        toplevel="axi4lite_regs",
        test_dir=Path(__file__).parent,
        parameters={"ADDR_WIDTH": ADDR_WIDTH, "DATA_WIDTH": DATA_WIDTH, "NUM_REGS": NUM_REGS},
    )
