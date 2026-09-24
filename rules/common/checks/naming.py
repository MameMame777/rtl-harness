"""Module names are lower_snake_case (and Verible's module-filename rule ties them to the
file name). Parameters, enums and signals are covered by Verible's own name-style rules."""

from __future__ import annotations

import re
from pathlib import Path

RULE = "module-name-style"
_MODULE_RX = re.compile(r"^\s*(?:module|interface|package)\s+(?:automatic\s+|static\s+)?([A-Za-z_][A-Za-z0-9_$]*)", re.MULTILINE)
_LOWER_SNAKE_RX = re.compile(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*")


def check(path: Path, text: str) -> list[dict]:
    out: list[dict] = []
    for m in _MODULE_RX.finditer(text):
        name = m.group(1)
        if not _LOWER_SNAKE_RX.fullmatch(name):
            out.append({"line": text.count("\n", 0, m.start()) + 1, "col": 1, "message": f"{name}: module/interface/package names are lower_snake_case"})
    return out
