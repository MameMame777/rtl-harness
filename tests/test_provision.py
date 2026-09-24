"""provision: add-if-missing, GitHub items only with a remote, idempotent."""

from __future__ import annotations

import subprocess
from pathlib import Path

from rtl_harness import provision
from rtl_harness.config import load_config


def test_without_remote_only_local_items(consumer: Path):
    cfg = load_config(consumer)
    missing = provision.plan(cfg)
    assert {m["path"] for m in missing} == {"tickets/README.md", "tickets/.gitkeep"}
    added = provision.apply(cfg, missing)
    assert set(added) == {"tickets/README.md", "tickets/.gitkeep"}
    assert (consumer / "tickets" / "README.md").read_text(encoding="utf-8").startswith("# tickets/")
    assert provision.plan(cfg) == []
    assert provision.apply(cfg, provision.plan(cfg)) == []


def test_with_github_remote_adds_forms_and_labels(consumer: Path):
    subprocess.run(["git", "init", "-q"], cwd=str(consumer), check=True)
    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/acme/proj.git"],
        cwd=str(consumer),
        check=True,
    )
    (consumer / "harness.toml").write_text(
        (consumer / "harness.toml").read_text()
        + '\n[tickets]\nescalate_repo = "acme/rtl-harness"\n'
    )
    cfg = load_config(consumer)
    assert provision.repo_slug(consumer) == "acme/proj"
    paths = {m["path"] for m in provision.plan(cfg)}
    assert ".github/ISSUE_TEMPLATE/rtl-bug.yml" in paths and ".github/labels.yml" in paths
    added = provision.apply(cfg, provision.plan(cfg))
    assert ".github/workflows/labels-sync.yml" in added
    cfg_yml = (consumer / ".github" / "ISSUE_TEMPLATE" / "config.yml").read_text(encoding="utf-8")
    assert "acme/rtl-harness" in cfg_yml and "{{" not in cfg_yml


def test_existing_files_are_never_overwritten(consumer: Path):
    (consumer / "tickets").mkdir()
    (consumer / "tickets" / "README.md").write_text("mine", encoding="utf-8")
    cfg = load_config(consumer)
    provision.apply(cfg, provision.plan(cfg))
    assert (consumer / "tickets" / "README.md").read_text(encoding="utf-8") == "mine"
