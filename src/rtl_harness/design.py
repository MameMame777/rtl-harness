"""list_design (P5): modules, parameters, ports and instances of the design.

This pass ships the contract (docs/tool-schema.md, shaped after RTLScope's dump-ports output
so the implementation can later be swapped for `rtlscope`) and an honest stub. P5 implements
it with `verilator --xml-only` and a regex fallback (source.tool says which one answered).
"""

from __future__ import annotations

from ._safety import rel, within
from .config import Config, design_files, load_config


def list_design(files: list[str] | None = None, top: str | None = None, cfg: Config | None = None) -> dict:
    cfg = cfg or load_config()
    targets = [within(cfg.root, f) for f in files] if files else design_files(cfg)
    return {
        "status": "unimplemented",
        "phase": "P5",
        "top": top or cfg.top or "",
        "modules": [],
        "source": {"tool": "none", "files": [rel(cfg.root, t) for t in targets]},
    }
