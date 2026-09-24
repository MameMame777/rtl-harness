#!/usr/bin/env python3
"""Repository hygiene for a public repo: no hardcoded absolute paths, internal URLs, personal
e-mail addresses or public IP addresses. Standard library only; used by CI and pre-commit.

    python scripts/ci/hygiene.py --diff origin/main...HEAD   # added lines only
    python scripts/ci/hygiene.py --all                       # every tracked text file
    python scripts/ci/hygiene.py --files a.py b.md           # given files (pre-commit)

Exit status 1 when findings exist. A line containing ``hygiene-ok`` is skipped; use it only
with a comment that says why (e.g. ``# hygiene-ok: well-known install roots``).
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Files that intentionally show BAD examples or contain the patterns themselves.
EXCLUDE_PREFIXES = (
    "SECURITY.md",
    "CONTRIBUTING.md",
    ".github/pull_request_template.md",
    ".gitleaks.toml",
    "docs/plan/",
    "scripts/ci/hygiene.py",
)

CHECKS: dict[str, re.Pattern[str]] = {
    "hardcoded-path": re.compile(r"([A-Z]:\\|/home/[a-z]|/Users/[A-Za-z])[A-Za-z0-9_./\\-]{3,}"),
    "internal-url": re.compile(r"(?i)(https?|ftp)://[a-z0-9._-]+\.(local|internal|corp|intranet|lan)\b"),
    "email": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "public-ip": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
}

# Matches that are fine even where the check fires.
ALLOW: dict[str, re.Pattern[str]] = {
    "hardcoded-path": re.compile(r"<[^>]+>|\$env:|\$HOME|\$PWD|PLACEHOLDER"),
    "email": re.compile(r"noreply@github\.com|users\.noreply\.github\.com|@example\.(com|org)"),
    "public-ip": re.compile(r"^(127\.|0\.0\.0\.0|192\.168\.|10\.|172\.(1[6-9]|2\d|3[01])\.|255\.)"),
}

SKIP_MARKER = "hygiene-ok"


def _excluded(path: str) -> bool:
    p = path.replace("\\", "/")
    return any(p == e or p.startswith(e) for e in EXCLUDE_PREFIXES)


def scan_line(path: str, lineno: int, text: str) -> list[tuple[str, str, int, str]]:
    if SKIP_MARKER in text:
        return []
    out = []
    for name, rx in CHECKS.items():
        for m in rx.finditer(text):
            token = m.group(0)
            allow = ALLOW.get(name)
            if allow and allow.search(token):
                continue
            if name == "hardcoded-path" and allow and allow.search(text):
                continue
            out.append((name, path, lineno, token))
    return out


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True, encoding="utf-8", errors="replace").stdout


def scan_diff(rng: str) -> list[tuple[str, str, int, str]]:
    findings = []
    path = None
    lineno = 0
    for line in _git("diff", "--unified=0", "--no-color", rng).splitlines():
        if line.startswith("+++ "):
            path = line[4:].removeprefix("b/") if line != "+++ /dev/null" else None
            continue
        if line.startswith("@@"):
            m = re.search(r"\+(\d+)", line)
            lineno = int(m.group(1)) if m else 0
            continue
        if line.startswith("+") and not line.startswith("+++") and path and not _excluded(path):
            findings += scan_line(path, lineno, line[1:])
            lineno += 1
    return findings


def scan_files(paths: list[str]) -> list[tuple[str, str, int, str]]:
    findings = []
    for p in paths:
        rel = str(Path(p)).replace("\\", "/")
        if _excluded(rel):
            continue
        fp = ROOT / p
        if not fp.is_file():
            continue
        try:
            text = fp.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue  # binary or unreadable: not a text hygiene target
        for i, line in enumerate(text.splitlines(), 1):
            findings += scan_line(rel, i, line)
    return findings


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--diff", metavar="RANGE", help="scan added lines of `git diff RANGE`")
    g.add_argument("--all", action="store_true", help="scan every tracked text file")
    g.add_argument("--files", nargs="+", help="scan the given files")
    ap.add_argument("--report-file", help="also write a markdown report here")
    args = ap.parse_args(argv)

    if args.diff:
        findings = scan_diff(args.diff)
    elif args.all:
        findings = scan_files(_git("ls-files").splitlines())
    else:
        findings = scan_files(args.files)

    if not findings:
        print("hygiene: no findings")
        if args.report_file:
            Path(args.report_file).write_text("### Hygiene\n\nno findings\n", encoding="utf-8")
        return 0

    lines = ["### Hygiene findings", "", "| check | file | line | token |", "|---|---|---|---|"]
    for name, path, lineno, token in findings:
        print(f"{path}:{lineno}: {name}: {token}")
        lines.append(f"| {name} | {path} | {lineno} | `{token}` |")
    if args.report_file:
        Path(args.report_file).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"hygiene: {len(findings)} finding(s). Use placeholders, or mark a justified line with '{SKIP_MARKER}'.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
