"""get_waveform (P5): return only the requested signals over a time window from a VCD.

This pass ships the contract (docs/tool-schema.md) and an honest stub: the MCP tool and the
CLI answer with status "unimplemented" and never truncate silently once implemented ("clipped"
counts the dropped value changes). The waveform path must live under <consumer>/.harness/.
"""

from __future__ import annotations

from ._safety import within
from .config import Config, load_config
from .errors import SafetyError


def get_waveform(
    waveform_path: str,
    signals: list[str],
    t_start: int = 0,
    t_end: int | None = None,
    max_changes: int = 200,
    cfg: Config | None = None,
) -> dict:
    cfg = cfg or load_config()
    p = within(cfg.root, waveform_path)
    runtime = cfg.runtime.resolve()
    if runtime != p and runtime not in p.parents:
        raise SafetyError("waveform_path must be under the project's .harness/ directory")
    return {
        "status": "unimplemented",
        "phase": "P5",
        "signals": [{"name": s, "width": None, "changes": []} for s in signals],
        "clipped": 0,
        "time_unit": "ps",
        "t_start": t_start,
        "t_end": t_end,
        "missing": list(signals),
        "source": {"waveform_path": p.relative_to(cfg.root).as_posix(), "max_changes": max_changes},
    }
