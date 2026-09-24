#!/usr/bin/env python3
"""evals runner (P4 skeleton).

    python evals/runner/run.py --dry-run                 list tasks and models from config.toml
    python evals/runner/run.py --model claude --task bus/001-sync_fifo   (P4)

Each attempt: hand task.md + ports.sv to the model through its adapter, collect the RTL it
writes, run rtl_harness.lint and rtl_harness.sim on it, record pass/fail and warning counts.
"""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVALS = HERE.parent


def load_config() -> dict:
    return tomllib.loads((HERE / "config.toml").read_text(encoding="utf-8"))


def list_tasks() -> list[str]:
    out = []
    for domain in ("bus", "cpu", "verif"):
        d = EVALS / domain
        if d.is_dir():
            out += [f"{domain}/{p.name}" for p in sorted(d.iterdir()) if p.is_dir() and (p / "task.md").is_file()]
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--model")
    ap.add_argument("--task")
    args = ap.parse_args(argv)
    cfg = load_config()
    if args.dry_run or not (args.model and args.task):
        print(json.dumps({"models": sorted(cfg["models"]), "tasks": list_tasks(), "run": cfg["run"]}, indent=2))
        return 0
    print("evals: model runs are implemented in P4 (see evals/README.md)", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
