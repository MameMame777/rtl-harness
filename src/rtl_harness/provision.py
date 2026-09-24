"""rtl-harness provision: give a consumer project the ticketing scaffolding it lacks.

Add-if-missing only: an existing file is never touched. Items that need GitHub (issue forms,
labels, the label-sync workflow, the PR template) are proposed only when the project has a
GitHub remote; the local tickets/ store is always proposed.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from . import paths
from .config import Config

TEMPLATES = paths.harness_root() / "scripts" / "provision"

# (destination in the consumer, template under scripts/provision, why, needs a GitHub remote)
ITEMS: list[tuple[str, str, str, bool]] = [
    (
        "tickets/README.md",
        "tickets/README.md",
        "local ticket store (rtl-harness ticket new)",
        False,
    ),
    ("tickets/.gitkeep", "tickets/gitkeep", "keeps tickets/ in git", False),
    (
        ".github/ISSUE_TEMPLATE/rtl-bug.yml",
        "ISSUE_TEMPLATE/rtl-bug.yml",
        "issue form: RTL bug",
        True,
    ),
    (
        ".github/ISSUE_TEMPLATE/ai-deviation.yml",
        "ISSUE_TEMPLATE/ai-deviation.yml",
        "issue form: AI deviation",
        True,
    ),
    (
        ".github/ISSUE_TEMPLATE/rule-proposal.yml",
        "ISSUE_TEMPLATE/rule-proposal.yml",
        "issue form: rule proposal",
        True,
    ),
    (
        ".github/ISSUE_TEMPLATE/tool-bug.yml",
        "ISSUE_TEMPLATE/tool-bug.yml",
        "issue form: harness tool bug",
        True,
    ),
    (
        ".github/ISSUE_TEMPLATE/config.yml",
        "ISSUE_TEMPLATE/config.yml",
        "issue chooser config",
        True,
    ),
    (".github/labels.yml", "labels.yml", "kind:* / domain:* / harness labels", True),
    (
        ".github/workflows/labels-sync.yml",
        "labels-sync.yml",
        "syncs labels.yml to the repository",
        True,
    ),
    (
        ".github/pull_request_template.md",
        "pull_request_template.md",
        "PR checklist incl. security self-review",
        True,
    ),
]


def github_remote(root: Path) -> str | None:
    try:
        r = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=str(root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    url = r.stdout.strip()
    return url if r.returncode == 0 and "github.com" in url else None


def repo_slug(root: Path) -> str | None:
    """owner/name from the origin URL (https or ssh), else None."""
    url = github_remote(root)
    if not url:
        return None
    tail = url.split("github.com", 1)[1].lstrip(":/")
    tail = tail.removesuffix(".git").rstrip("/")
    return tail if tail.count("/") == 1 else None


def plan(cfg: Config) -> list[dict]:
    has_gh = github_remote(cfg.root) is not None
    missing = []
    for dest, src, why, needs_gh in ITEMS:
        if needs_gh and not has_gh:
            continue
        if not (cfg.root / dest).exists():
            missing.append({"path": dest, "template": src, "why": why})
    return missing


def _render(text: str, cfg: Config) -> str:
    slug = repo_slug(cfg.root) or "<owner>/<repo>"
    return (
        text.replace("{{escalate_repo}}", cfg.escalate_repo or "<owner>/rtl-harness")
        .replace("{{project_repo}}", slug)
        .replace("{{tickets_dir}}", cfg.tickets_dir)
    )


def apply(cfg: Config, missing: list[dict]) -> list[str]:
    added = []
    for item in missing:
        src = TEMPLATES / item["template"]
        dest = cfg.root / item["path"]
        if dest.exists() or not src.is_file():
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(
            _render(src.read_text(encoding="utf-8"), cfg), encoding="utf-8", newline="\n"
        )
        added.append(item["path"])
    return added
