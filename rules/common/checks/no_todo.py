"""No placeholders: TODO / FIXME / XXX / HACK markers are not allowed in committed RTL.
Open a ticket instead (rtl-harness ticket new)."""

from __future__ import annotations

import re
from pathlib import Path

RULE = "no-todo"
_MARKER_RX = re.compile(r"\b(TODO|FIXME|XXX|HACK)\b")


def check(path: Path, text: str) -> list[dict]:
    out: list[dict] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        m = _MARKER_RX.search(line)
        if m:
            out.append({"line": lineno, "col": m.start() + 1, "message": f"{m.group(1)} marker: finish the code or open a ticket"})
    return out
