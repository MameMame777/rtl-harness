"""Clock + reset bring-up for the harness convention: synchronous active-low `rst_n`,
100 MHz default single clock. Always drive clocks with cocotb.clock.Clock -- never with a
sub-timestep polling loop (a gated clock would then take hours to reach a timeout)."""

from __future__ import annotations

from cocotb.clock import Clock
from cocotb.triggers import ClockCycles


def start_clock(clk, period_ns: float = 10.0, start_high: bool = False):
    """Start driving *clk* and return the clock Task. 10 ns = 100 MHz."""
    return Clock(clk, period_ns, unit="ns").start(start_high=start_high)


async def reset_active_low(clk, rst_n, cycles: int = 8, post: int = 2) -> None:
    """Hold rst_n low for *cycles* clocks, release, settle *post* clocks."""
    rst_n.value = 0
    await ClockCycles(clk, cycles)
    rst_n.value = 1
    if post:
        await ClockCycles(clk, post)


async def bringup(
    dut,
    clk: str = "clk",
    rst: str = "rst_n",
    period_ns: float = 10.0,
    cycles: int = 8,
    post: int = 2,
):
    """Start the clock and apply the synchronous active-low reset. Returns (clk, rst_n)."""
    clk_sig = getattr(dut, clk)
    rst_sig = getattr(dut, rst)
    start_clock(clk_sig, period_ns)
    await reset_active_low(clk_sig, rst_sig, cycles, post)
    return clk_sig, rst_sig


async def bringup_dual(
    dut,
    clk_a: str,
    rst_a: str,
    clk_b: str,
    rst_b: str,
    period_a_ns: float = 10.0,
    period_b_ns: float = 14.0,
):
    """Two-clock bring-up for CDC blocks. Both clocks start first, then the resets release one
    after the other so neither domain samples the other while still in reset."""
    ca, ra = getattr(dut, clk_a), getattr(dut, rst_a)
    cb, rb = getattr(dut, clk_b), getattr(dut, rst_b)
    start_clock(ca, period_a_ns)
    start_clock(cb, period_b_ns)
    ra.value = 0
    rb.value = 0
    await ClockCycles(ca, 8)
    ra.value = 1
    await ClockCycles(cb, 8)
    rb.value = 1
    await ClockCycles(cb, 4)
    return (ca, ra), (cb, rb)


async def bringup_n(dut, specs, *, low_cycles: int = 8, stagger: bool = True):
    """N-clock active-low bring-up. specs = [(clk_name, rstn_name, period_ns), ...].
    Returns [(clk_handle, rstn_handle), ...] in the given order."""
    pairs = []
    for clk_name, rstn_name, period in specs:
        clk = getattr(dut, clk_name)
        rstn = getattr(dut, rstn_name)
        start_clock(clk, period)
        rstn.value = 0
        pairs.append((clk, rstn))
    ref = pairs[0][0]
    await ClockCycles(ref, low_cycles)
    if stagger:
        for clk, rstn in pairs:
            rstn.value = 1
            await ClockCycles(clk, max(1, low_cycles // 2))
    else:
        for _, rstn in pairs:
            rstn.value = 1
    await ClockCycles(ref, 4)
    return pairs
