"""Detect newly added lint suppressions (Verilator lint_off, Verible waive/format-off, waiver
file edits). Used by run_lint (working tree vs HEAD) and by the CI lint-off job (PR range)."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

SUPPRESSION_RX = re.compile(
    r"verilator\s+lint_(off|save|restore)|verilog_lint:\s*waive|verilog_format:\s*off|verilog_syntax:\s*",
    re.IGNORECASE,
)
WAIVER_FILE_RX = re.compile(r"(^|/)(waivers?\.verible|[^/]+\.waiver)$")
SOURCE_RX = re.compile(r"\.(sv|svh|v|vh)$", re.IGNORECASE)


def _git(root: Path, *args: str) -> str | None:
    try:
        r = subprocess.run(
            ["git", *args],
            cwd=str(root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout if r.returncode == 0 else None


def _added_lines(root: Path, rng: str, paths: list[str] | None) -> list[tuple[str, int, str]]:
    diff = _git(
        root, "diff", "--unified=0", "--no-color", "--diff-filter=AM", rng, "--", *(paths or [])
    )
    out: list[tuple[str, int, str]] = []
    if diff is None:
        return out
    path = None
    lineno = 0
    for line in diff.splitlines():
        if line.startswith("+++ "):
            path = None if line == "+++ /dev/null" else line[4:].removeprefix("b/")
            continue
        if line.startswith("@@"):
            m = re.search(r"\+(\d+)", line)
            lineno = int(m.group(1)) if m else 0
            continue
        if line.startswith("+") and not line.startswith("+++") and path:
            out.append((path, lineno, line[1:]))
            lineno += 1
    return out


def _untracked(root: Path, paths: list[str] | None) -> list[tuple[str, int, str]]:
    listing = _git(root, "ls-files", "--others", "--exclude-standard", "--", *(paths or []))
    out: list[tuple[str, int, str]] = []
    for rel in (listing or "").splitlines():
        if not (SOURCE_RX.search(rel) or WAIVER_FILE_RX.search(rel)):
            continue
        try:
            text = (root / rel).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        out.extend((rel, i, t) for i, t in enumerate(text.splitlines(), 1))
    return out


def scan(
    root: Path, rng: str = "HEAD", paths: list[str] | None = None, include_untracked: bool = True
) -> list[dict]:
    """Suppressions added relative to *rng* (a commit, or 'base...HEAD' for a PR).
    Returns [{file, line, text}]; an empty list when not inside a git repository."""
    added = _added_lines(root, rng, paths)
    if include_untracked:
        added += _untracked(root, paths)
    findings = []
    seen_waivers: set[str] = set()
    for path, lineno, text in added:
        if WAIVER_FILE_RX.search(path):
            if path not in seen_waivers:
                seen_waivers.add(path)
                findings.append({"file": path, "line": lineno, "text": "waiver file changed"})
            continue
        if SOURCE_RX.search(path) and SUPPRESSION_RX.search(text):
            findings.append({"file": path, "line": lineno, "text": text.strip()[:200]})
    return findings
