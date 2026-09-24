"""CPU rule: combinational decode uses `unique case` (or `priority case`).

A plain `case` inside always_comb silently allows overlapping or missing items; `unique`
makes the simulator and the synthesizer check that exactly one item matches, which is what a
decoder means. Detected textually inside always_comb blocks.
"""

from __future__ import annotations

import re
from pathlib import Path

RULE = "unique-case"
_COMB_RX = re.compile(r"always_comb\b")
_CASE_RX = re.compile(r"(?<![A-Za-z_])(unique\s+|priority\s+|unique0\s+)?case[xz]?\s*\(")
_END_RX = re.compile(r"\b(always_ff|always_comb|always_latch|endmodule)\b")


def check(path: Path, text: str) -> list[dict]:
    out: list[dict] = []
    for m in _COMB_RX.finditer(text):
        end = _END_RX.search(text, m.end())
        block = text[m.end():end.start() if end else len(text)]
        for c in _CASE_RX.finditer(block):
            if c.group(1) is None:
                pos = m.end() + c.start()
                out.append({"line": text.count("\n", 0, pos) + 1, "col": 1, "message": "use `unique case` (or `priority case`) for combinational decode"})
    return out
