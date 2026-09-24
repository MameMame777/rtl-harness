"""Every RTL file starts with `timescale 1ns / 1ps (first non-blank, non-comment line)."""

from __future__ import annotations

import re
from pathlib import Path

RULE = "timescale"
_TIMESCALE_RX = re.compile(r"^\s*`timescale\s+1\s*ns\s*/\s*1\s*ps\s*$")
_EXPECTED = "`timescale 1ns / 1ps"


def check(path: Path, text: str) -> list[dict]:
    if path.suffix.lower() == ".svh":
        return []  # header files are included into a file that already has a timescale
    in_block = False
    for lineno, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if in_block:
            if "*/" in s:
                in_block = False
            continue
        if not s or s.startswith("//"):
            continue
        if s.startswith("/*"):
            in_block = "*/" not in s
            continue
        if _TIMESCALE_RX.match(s):
            return []
        return [{"line": lineno, "col": 1, "message": f"first statement must be {_EXPECTED}"}]
    return [{"line": 1, "col": 1, "message": f"file has no {_EXPECTED} directive"}]
