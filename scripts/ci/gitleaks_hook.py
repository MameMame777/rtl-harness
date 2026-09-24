#!/usr/bin/env python3
"""pre-commit hook: run the pinned gitleaks (from <harness>/.tools or PATH) on the staged
changes. Fails the commit when a secret is found; prints how to install gitleaks when it is
missing instead of silently passing."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rtl_harness import paths  # noqa: E402


def main() -> int:
    exe = paths.gitleaks()
    if exe is None:
        print(
            "gitleaks not found: run scripts/install_gitleaks.ps1 (or scripts/ci/install_gitleaks.sh)",
            file=sys.stderr,
        )
        return 1
    cfg = paths.harness_root() / ".gitleaks.toml"
    args = [str(exe), "git", "--pre-commit", "--staged", "--redact", "--exit-code", "1"]
    if cfg.is_file():
        args += ["--config", str(cfg)]
    return subprocess.run(args, cwd=str(Path.cwd()), shell=False).returncode


if __name__ == "__main__":
    sys.exit(main())
