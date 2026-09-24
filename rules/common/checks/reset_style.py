"""Reset convention: synchronous, active-low `rst_n`.

  always_ff @(posedge clk) begin
      if (!rst_n) begin ... end else begin ... end
  end

Findings: an asynchronous reset in the sensitivity list (negedge / or), a sequential block
whose first statement is not `if (!<...>rst_n)`, or an active-high / positive-polarity check.
"""

from __future__ import annotations

import re
from pathlib import Path

RULE = "reset-style"

_ALWAYS_FF_RX = re.compile(r"always_ff\s*@\s*\((?P<sens>[^)]*)\)\s*(?:begin\b)?", re.MULTILINE)
_FIRST_IF_RX = re.compile(r"\s*(?://[^\n]*\n\s*)*if\s*\((?P<cond>[^)]*)\)")
_RESET_OK_RX = re.compile(r"^\s*!\s*(?:[a-z][a-z0-9_]*_)?rst_n\s*$")
_RESET_LIKE_RX = re.compile(r"(^|[^a-z0-9_])(rst|reset|aresetn|rst_n|resetn)([^a-z0-9_]|$)", re.IGNORECASE)


def _lineno(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def check(path: Path, text: str) -> list[dict]:
    out: list[dict] = []
    for m in _ALWAYS_FF_RX.finditer(text):
        line = _lineno(text, m.start())
        sens = " ".join(m.group("sens").split())
        if "negedge" in sens or " or " in f" {sens} " or "," in sens:
            out.append({"line": line, "col": 1, "message": f"asynchronous reset in sensitivity list ({sens}); use always_ff @(posedge clk) with a synchronous rst_n"})
            continue
        f = _FIRST_IF_RX.match(text, m.end())
        if not f:
            continue  # no reset branch at all: allowed for pure pipeline registers
        cond = f.group("cond").strip()
        if _RESET_OK_RX.match(cond):
            continue
        if _RESET_LIKE_RX.search(cond):
            out.append({"line": _lineno(text, f.start()), "col": 1, "message": f"reset must be checked as `if (!rst_n)` (synchronous, active-low), found `if ({cond})`"})
    return out
