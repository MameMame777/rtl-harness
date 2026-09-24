"""valid/ready handshake helpers for ports named <prefix>_valid / <prefix>_ready / <prefix>_data
(the BUS-domain convention; see docs/bus.md).

    ValidReadySource(dut, clk, "s")   drives s_valid/s_data, holds them until s_ready
    ValidReadySink(dut, clk, "m")     drives m_ready (optionally with random backpressure)
    ValidReadyMonitor(dut, clk, "m")  records every accepted beat (valid & ready at a rising edge)

Sampling convention (proven with cocotb 2.0 + Verilator): read signals right after
`await RisingEdge(clk)` -- that is the value the edge sampled -- and write new values in the
same step so they are seen by the next edge. A source never looks at `ready` before asserting
`valid` (the protocol forbids a valid that depends on ready).
"""

from __future__ import annotations

import cocotb
from cocotb.triggers import RisingEdge

from .gap import GapPolicy, default_gap_policy


class ValidReadySource:
    def __init__(self, dut, clk, prefix: str = "s") -> None:
        self.clk = clk
        self.valid = getattr(dut, f"{prefix}_valid")
        self.ready = getattr(dut, f"{prefix}_ready")
        self.data = getattr(dut, f"{prefix}_data")
        self.sent: list[int] = []
        self.valid.value = 0
        self.data.value = 0

    async def send_all(self, items, gap_policy: GapPolicy | None = None) -> None:
        """Offer the beats back to back; each is held until accepted. With an active gap
        policy, idle cycles (valid low) are inserted before beats."""
        pol = gap_policy if gap_policy is not None else default_gap_policy()
        for d in items:
            gap = pol.next_gap() if pol.active else 0
            if gap:
                self.valid.value = 0
                for _ in range(gap):
                    await RisingEdge(self.clk)
            self.data.value = int(d)
            self.valid.value = 1
            while True:
                await RisingEdge(self.clk)
                if int(self.ready.value) == 1:  # accepted at this edge
                    break
            self.sent.append(int(d))
        self.valid.value = 0

    async def send(self, data: int, gap_policy: GapPolicy | None = None) -> None:
        await self.send_all([data], gap_policy)


class ValidReadySink:
    def __init__(self, dut, clk, prefix: str = "m", ready: bool = True) -> None:
        self.clk = clk
        self.ready = getattr(dut, f"{prefix}_ready")
        self.ready.value = 1 if ready else 0
        self._task = None

    def set_ready(self, value: bool) -> None:
        self.ready.value = 1 if value else 0

    def start_backpressure(self, gap_policy: GapPolicy | None = None):
        """ready high for one cycle, low for next_gap() cycles, repeat."""
        pol = gap_policy if gap_policy is not None else default_gap_policy()
        self._task = cocotb.start_soon(self._run(pol))
        return self._task

    async def _run(self, pol: GapPolicy) -> None:
        while True:
            self.ready.value = 1
            await RisingEdge(self.clk)
            if not pol.active:
                continue
            gap = pol.next_gap()
            if gap:
                self.ready.value = 0
                for _ in range(gap):
                    await RisingEdge(self.clk)


class ValidReadyMonitor:
    def __init__(self, dut, clk, prefix: str = "m") -> None:
        self.clk = clk
        self.valid = getattr(dut, f"{prefix}_valid")
        self.ready = getattr(dut, f"{prefix}_ready")
        self.data = getattr(dut, f"{prefix}_data")
        self.beats: list[int] = []

    def start(self):
        return cocotb.start_soon(self._run())

    async def _run(self) -> None:
        while True:
            await RisingEdge(self.clk)
            if int(self.valid.value) == 1 and int(self.ready.value) == 1:
                self.beats.append(int(self.data.value))
