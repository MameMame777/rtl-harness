"""run_lint: formatter -> Verible lint -> Verilator lint -> custom checks -> severity map.

One code path for the CLI, the MCP server, pre-commit and CI, so all of them return the same
JSON (docs/tool-schema.md). The result is also written to <consumer>/.harness/last/lint.json.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from . import lintoff, paths, rules
from ._proc import run
from ._safety import clean_env, rel, within
from .config import Config, design_files, load_config
from .errors import ToolMissing

TOOL_TIMEOUT_S = 300

# "path:line:col: message [rule]"   (Verible; the last bracket group is the rule name)
_VERIBLE_RX = re.compile(r"^(?P<file>.+?):(?P<line>\d+):(?P<col>\d+)(?:-\d+)?:\s*(?P<msg>.*?)\s*(?:\[(?P<rule>[a-z0-9-]+)\])?\s*$")
# "%Warning-CODE: path:line:col: message"  /  "%Error: path:line:col: message"  (Verilator)
_VERILATOR_RX = re.compile(r"^%(?P<kind>Warning|Error)(?:-(?P<code>[A-Za-z0-9_]+))?:\s*(?:(?P<file>(?:[A-Za-z]:)?[^:\s][^:]*?):(?P<line>\d+):(?P<col>\d+):)?\s*(?P<msg>.*)$")


@dataclass
class Finding:
    file: str
    line: int
    col: int
    rule: str
    message: str
    severity: str
    tool: str


def _posix(p: Path) -> str:
    return str(p).replace("\\", "/")


def _resolve_targets(files: list[str] | None, cfg: Config) -> list[Path]:
    if not files:
        return design_files(cfg)
    out: list[Path] = []
    for f in files:
        p = within(cfg.root, f)
        if p.is_dir():
            out.extend(q for q in sorted(p.rglob("*")) if q.is_file() and q.suffix.lower() in (".sv", ".svh", ".v", ".vh"))
        elif p.is_file():
            out.append(p)
        else:
            raise ToolMissing(f"no such file: {f}")
    seen: dict[str, Path] = {}
    for p in out:
        seen.setdefault(str(p), p)
    return list(seen.values())


# --- stages ----------------------------------------------------------------------------------

def _format(targets: list[Path], cfg: Config, fix: bool) -> tuple[list[str], list[Finding]]:
    exe = paths.verible("verible-verilog-format")
    flags = rules.verible_format_flags()
    changed: list[str] = []
    findings: list[Finding] = []
    env = clean_env()
    for t in targets:
        r = run([exe, f"--flagfile={_posix(flags)}", _posix(t)], cwd=cfg.root, env=env, timeout_s=TOOL_TIMEOUT_S)
        if not r.ok:
            # A file the formatter cannot parse: the lint stage reports the syntax error.
            continue
        original = t.read_text(encoding="utf-8", errors="replace")
        if r.stdout != original:
            changed.append(rel(cfg.root, t))
            if fix:
                t.write_text(r.stdout, encoding="utf-8", newline="\n")
    return changed, findings


def _verible_lint(targets: list[Path], cfg: Config) -> list[Finding]:
    if not targets:
        return []
    exe = paths.verible("verible-verilog-lint")
    args = [exe, f"--rules_config={_posix(rules.verible_rules_file())}", "--lint_fatal=false", "--parse_fatal=false"]
    waivers = rules.waiver_files(cfg)
    if waivers:
        args.append("--waiver_files=" + ",".join(_posix(w) for w in waivers))
    args += [_posix(t) for t in targets]
    r = run(args, cwd=cfg.root, env=clean_env(), timeout_s=TOOL_TIMEOUT_S)
    out: list[Finding] = []
    for line in (r.stdout + "\n" + r.stderr).splitlines():
        m = _VERIBLE_RX.match(line.strip())
        if not m:
            continue
        rule = m.group("rule") or ("syntax-error" if "syntax error" in m.group("msg").lower() else "verible")
        out.append(Finding(_relpath(cfg, m.group("file")), int(m.group("line")), int(m.group("col")), rule, m.group("msg"), "", "verible"))
    return out


def _verilator_lint(targets: list[Path], cfg: Config) -> list[Finding]:
    if not targets:
        return []
    exe, extra_env, prepend = paths.verilator()
    args = [exe, *rules.verilator_flags()]
    args += [f"-I{_posix(within(cfg.root, i))}" for i in cfg.includes]
    args += [f"-D{d}" for d in cfg.defines]
    if cfg.top:
        args += ["--top-module", cfg.top]
    args += [_posix(t) for t in targets]
    r = run(args, cwd=cfg.root, env=clean_env(extra_env, prepend), timeout_s=TOOL_TIMEOUT_S)
    out: list[Finding] = []
    for line in (r.stdout + "\n" + r.stderr).splitlines():
        m = _VERILATOR_RX.match(line.strip())
        if not m:
            continue
        code = m.group("code") or ("ERROR" if m.group("kind") == "Error" else "WARNING")
        msg = m.group("msg").strip()
        if not msg or msg.startswith("...") or "See https://verilator.org" in msg or msg.startswith("Exiting due to"):
            continue
        file = _relpath(cfg, m.group("file")) if m.group("file") else ""
        out.append(Finding(file, int(m.group("line") or 0), int(m.group("col") or 0), code, msg, "", "verilator"))
    return out


def _custom(targets: list[Path], cfg: Config) -> list[Finding]:
    out: list[Finding] = []
    for mod in rules.load_checks(cfg):
        for t in targets:
            text = t.read_text(encoding="utf-8", errors="replace")
            for f in mod.check(t, text):
                out.append(Finding(rel(cfg.root, t), int(f.get("line", 0)), int(f.get("col", 0)), str(mod.RULE), str(f.get("message", "")), "", "custom"))
    return out


def _relpath(cfg: Config, file: str) -> str:
    p = Path(file)
    try:
        return rel(cfg.root, p if p.is_absolute() else cfg.root / p)
    except ValueError:
        return _posix(p)


# --- entry point -----------------------------------------------------------------------------

def run_lint(files: list[str] | None = None, *, fix: bool = False, cfg: Config | None = None) -> dict:
    """Lint (and optionally format) *files* (project-relative; default: every design file)."""
    cfg = cfg or load_config()
    started = time.perf_counter()
    targets = _resolve_targets(files, cfg)
    sev_map = rules.load_severities(cfg)

    changed, findings = _format(targets, cfg, fix)
    findings += _verible_lint(targets, cfg)
    findings += _verilator_lint(targets, cfg)
    findings += _custom(targets, cfg)
    for f in findings:
        f.severity = "error" if f.rule == "syntax-error" or f.rule == "ERROR" else rules.severity_for(sev_map, f.tool, f.rule)
    findings.sort(key=lambda f: (f.file, f.line, f.col, f.tool, f.rule))

    counts = {"error": sum(f.severity == "error" for f in findings), "warning": sum(f.severity == "warning" for f in findings)}
    rel_targets = [rel(cfg.root, t) for t in targets]
    result = {
        "status": "fail" if counts["error"] or (changed and not fix) else "pass",
        "formatter": {"changed": changed, "fixed": bool(fix)},
        "lint": {"errors": [asdict(f) for f in findings], "counts": counts},
        "lint_off_added": lintoff.scan(cfg.root, "HEAD", rel_targets),
        "source": {"rules_version": rules.rules_version(), "files": rel_targets, "duration_s": round(time.perf_counter() - started, 3)},
    }
    _save_last(cfg, "lint", result)
    return result


def _save_last(cfg: Config, name: str, result: dict) -> None:
    try:
        d = cfg.runtime / "last"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{name}.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
