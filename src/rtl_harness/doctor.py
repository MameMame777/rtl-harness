"""rtl-harness doctor: where things are, which tools are found, and what is missing."""

from __future__ import annotations

import sys
from pathlib import Path

from . import __version__, paths
from .config import design_files, load_config, test_files
from .errors import HarnessError

AGENTS_MAX_LINES = 100


def _try(fn, *args):
    try:
        return fn(*args), None
    except HarnessError as exc:
        return None, str(exc)


def report() -> dict:
    out: dict = {"harness_version": __version__, "harness_root": str(paths.harness_root()), "python": sys.version.split()[0], "problems": []}
    root, err = _try(paths.consumer_root)
    out["consumer_root"] = str(root) if root else None
    if err:
        out["problems"].append(err)
    cfg = None
    if root:
        cfg, err = _try(load_config, root)
        if err:
            out["problems"].append(err)
    if cfg:
        out["config"] = {
            "self_consumption": cfg.is_self,
            "domains": cfg.domains,
            "design_files": len(design_files(cfg)),
            "test_blocks": sorted(test_files(cfg)),
        }

    tools: dict[str, str | None] = {}
    for name in ("verible-verilog-lint", "verible-verilog-format"):
        p, err = _try(paths.verible, name)
        tools[name] = paths.tool_version(p) if p else None
        if err:
            out["problems"].append(err)
    v, err = _try(paths.verilator)
    tools["verilator"] = paths.tool_version(v[0]) if v else None
    if err:
        out["problems"].append(err)
    sp, err = _try(paths.sim_python)
    tools["sim_python"] = str(sp) if sp else None
    if err:
        out["problems"].append(err)
    gl = paths.gitleaks()
    tools["gitleaks"] = paths.tool_version(gl, "version") if gl else None
    out["tools"] = tools

    agents = paths.harness_root() / "AGENTS.md"
    if agents.is_file():
        n = len(agents.read_text(encoding="utf-8").splitlines())
        out["agents_md_lines"] = n
        if n > AGENTS_MAX_LINES:
            out["problems"].append(f"AGENTS.md has {n} lines (limit {AGENTS_MAX_LINES})")
    else:
        out["agents_md_lines"] = None

    if cfg:
        try:
            from .provision import plan

            missing = plan(cfg)
            out["provision_missing"] = [m["path"] for m in missing]
        except ImportError:
            pass
    out["status"] = "ok" if not out["problems"] else "problems"
    return out


def render(r: dict) -> str:
    lines = [f"rtl-harness {r['harness_version']}  (python {r['python']})",
             f"  harness root : {r['harness_root']}",
             f"  consumer root: {r.get('consumer_root')}"]
    if r.get("config"):
        c = r["config"]
        lines.append(f"  config       : self={c['self_consumption']} domains={c['domains']} design_files={c['design_files']} blocks={c['test_blocks']}")
    for k, v in r.get("tools", {}).items():
        lines.append(f"  {k:22s}: {v or 'MISSING'}")
    if r.get("agents_md_lines") is not None:
        lines.append(f"  AGENTS.md    : {r['agents_md_lines']} lines")
    if r.get("provision_missing"):
        lines.append("  provision    : missing " + ", ".join(r["provision_missing"]))
    for p in r["problems"]:
        lines.append(f"  ! {p}")
    lines.append(f"status: {r['status']}")
    return "\n".join(lines)


def agents_md_ok(path: Path | None = None) -> bool:
    p = path or paths.harness_root() / "AGENTS.md"
    return p.is_file() and len(p.read_text(encoding="utf-8").splitlines()) <= AGENTS_MAX_LINES
