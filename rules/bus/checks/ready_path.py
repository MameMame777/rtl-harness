"""BUS rule: ready should not pass through a block combinationally.

    assign s_ready = m_ready;                 // legal AXI, but chains into long ready paths
    assign s_ready = !skid_valid;             // preferred: ready comes from a register

Detected textually: an `assign <x>_ready =` whose right hand side references another
`*_ready`. Reported as a warning (see rules/bus/rules.toml); a skid buffer removes it.
"""

from __future__ import annotations

import re
from pathlib import Path

RULE = "combinational-ready-path"
_ASSIGN_RX = re.compile(r"(?:^|[;\n])\s*assign\s+([A-Za-z_][A-Za-z0-9_]*_ready)\s*=\s*([^;]*);", re.MULTILINE)
_READY_RX = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*_ready\b")


def check(path: Path, text: str) -> list[dict]:
    out: list[dict] = []
    for m in _ASSIGN_RX.finditer(text):
        lhs, rhs = m.group(1), m.group(2)
        others = [r for r in _READY_RX.findall(rhs) if r != lhs]
        if others:
            line = text.count("\n", 0, m.start(1)) + 1
            out.append({"line": line, "col": 1, "message": f"{lhs} is combinational from {others[0]}: register ready (skid buffer) to keep ready paths short"})
    return out
