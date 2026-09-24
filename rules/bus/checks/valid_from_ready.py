"""BUS rule: a valid signal must never depend on the corresponding ready.

    assign m_valid = s_valid && m_ready;      // wrong: valid waits for ready -> deadlock risk
    assign m_valid = out_valid;               // right: valid is a register (or a function of
                                              // upstream state only)

Detected textually: an `assign <x>_valid =` or a `<x>_valid =` inside always_comb whose right
hand side references any `*_ready` signal.
"""

from __future__ import annotations

import re
from pathlib import Path

RULE = "valid-depends-on-ready"
_ASSIGN_RX = re.compile(r"(?:^|[;\n])\s*(?:assign\s+)?([A-Za-z_][A-Za-z0-9_]*_valid)\s*=\s*([^;]*);", re.MULTILINE)
_READY_RX = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*_ready\b")


def check(path: Path, text: str) -> list[dict]:
    out: list[dict] = []
    for m in _ASSIGN_RX.finditer(text):
        rhs = m.group(2)
        hit = _READY_RX.search(rhs)
        if hit:
            line = text.count("\n", 0, m.start(1)) + 1
            out.append({"line": line, "col": 1, "message": f"{m.group(1)} depends on {hit.group(0)}: valid must not wait for ready (register the decision instead)"})
    return out
