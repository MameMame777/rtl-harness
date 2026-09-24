"""Command line entry point: `rtl-harness <command>`.

Exit codes: 0 pass, 1 the design failed a check, 2 the harness or a tool could not run.
"""

from __future__ import annotations

import argparse
import json
import sys

from . import __version__
from .errors import HarnessError


def _print_json(obj) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def _lint_text(r: dict) -> str:
    lines = []
    for f in r["lint"]["errors"]:
        loc = f"{f['file']}:{f['line']}:{f['col']}" if f["file"] else "(global)"
        lines.append(f"{loc}: {f['severity']}: {f['message']} [{f['tool']}/{f['rule']}]")
    for c in r["formatter"]["changed"]:
        lines.append(f"{c}: {'formatted' if r['formatter']['fixed'] else 'needs formatting (run with --fix)'}")
    for s in r["lint_off_added"]:
        lines.append(f"{s['file']}:{s['line']}: lint suppression added: {s['text']}")
    c = r["lint"]["counts"]
    lines.append(f"lint: {r['status'].upper()}  errors={c['error']} warnings={c['warning']} files={len(r['source']['files'])}")
    return "\n".join(lines)


def cmd_lint(args) -> int:
    from .lint import run_lint

    r = run_lint(args.files or None, fix=args.fix)
    _print_json(r) if args.json else print(_lint_text(r))
    return 0 if r["status"] == "pass" else 1


def cmd_lintoff(args) -> int:
    from . import lintoff, paths

    root = paths.consumer_root()
    found = lintoff.scan(root, args.range, None, include_untracked=not args.no_untracked)
    _print_json(found) if args.json else print("\n".join(f"{f['file']}:{f['line']}: {f['text']}" for f in found) or "no lint suppressions added")
    return 1 if found and args.fail else 0


def cmd_doctor(args) -> int:
    from . import doctor

    r = doctor.report()
    _print_json(r) if args.json else print(doctor.render(r))
    return 0 if r["status"] == "ok" else 1


def cmd_sim(args) -> int:
    from .sim import run_all, run_sim

    if args.all:
        r = run_all(waves=args.waves, timeout_s=args.timeout)
        if args.json:
            _print_json(r)
        else:
            for b in r["blocks"]:
                print(f"{b['source']['block']:28s} {b['status'].upper():12s} passed={b['passed']} failed={b['failed']} {b['duration_s']:.1f}s")
            print(f"sim: {r['status'].upper()}  blocks={len(r['blocks'])} failed={r['failed_blocks']}")
        return 0 if r["status"] == "pass" else 1
    if not args.block:
        print("sim: give a block name or --all", file=sys.stderr)
        return 2
    r = run_sim(args.block, waves=args.waves, timeout_s=args.timeout)
    if args.json:
        _print_json(r)
    else:
        print(f"sim {args.block}: {r['status'].upper()}  passed={r['passed']} failed={r['failed']} {r['duration_s']:.1f}s")
        if r.get("first_failure"):
            ff = r["first_failure"]
            print(f"  first failure: {ff['test']}: {ff['message']}")
        print(f"  log: {r['log_path']}" + (f"\n  waves: {r['waveform_path']}" if r.get("waveform_path") else ""))
    return 0 if r["status"] == "pass" else 1


def cmd_provision(args) -> int:
    from .config import load_config
    from .provision import apply, plan

    cfg = load_config()
    missing = plan(cfg)
    if args.check or args.dry_run:
        _print_json(missing) if args.json else print("\n".join(f"missing: {m['path']}  ({m['why']})" for m in missing) or "nothing to provision")
        return 1 if (missing and args.check) else 0
    added = apply(cfg, missing)
    _print_json(added) if args.json else print("\n".join(f"added: {a}" for a in added) or "nothing to provision")
    return 0


def cmd_ticket(args) -> int:
    from . import ticket

    return ticket.cli(args)


def cmd_sync(args) -> int:
    from . import sync

    return sync.cli(args)


def cmd_stub(name: str):
    def _run(args) -> int:
        print(f"{name}: not implemented in this pass (see docs/tool-schema.md for the contract)", file=sys.stderr)
        return 2
    return _run


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="rtl-harness", description="Shared AI-agent harness for RTL design.")
    p.add_argument("--version", action="version", version=f"rtl-harness {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("lint", help="format check + Verible + Verilator + custom checks")
    s.add_argument("files", nargs="*", help="project-relative files or directories (default: all design files)")
    s.add_argument("--fix", action="store_true", help="rewrite files with the formatter")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_lint)

    s = sub.add_parser("lintoff", help="list lint suppressions added since a git ref")
    s.add_argument("--range", default="HEAD", help="git ref or A...B range (default HEAD = working tree)")
    s.add_argument("--no-untracked", action="store_true")
    s.add_argument("--fail", action="store_true", help="exit 1 when any suppression was added")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_lintoff)

    s = sub.add_parser("sim", help="build and run one cocotb block (or --all)")
    s.add_argument("block", nargs="?")
    s.add_argument("--all", action="store_true")
    s.add_argument("--waves", action="store_true")
    s.add_argument("--timeout", type=float, default=600.0, help="seconds per block")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_sim)

    s = sub.add_parser("doctor", help="show roots, tools and problems")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_doctor)

    s = sub.add_parser("provision", help="add the ticketing scaffolding a project lacks")
    s.add_argument("--check", action="store_true", help="exit 1 if anything is missing")
    s.add_argument("--dry-run", action="store_true")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_provision)

    s = sub.add_parser("ticket", help="record a problem as a ticket (and a GitHub issue)")
    from .ticket import add_arguments as _ticket_args

    _ticket_args(s)
    s.set_defaults(func=cmd_ticket)

    s = sub.add_parser("sync", help="generate the per-tool entry files of a consumer project")
    s.add_argument("--check", action="store_true", help="exit 1 if generated files are stale")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_sync)

    for name in ("wave", "design"):
        s = sub.add_parser(name, help=f"{name}: stub (P5)")
        s.add_argument("args", nargs="*")
        s.set_defaults(func=cmd_stub(name))
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except HarnessError as exc:
        print(f"rtl-harness: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
