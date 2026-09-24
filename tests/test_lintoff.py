"""lintoff: added suppressions are detected in the working tree, untracked files and waiver edits."""

from __future__ import annotations

import subprocess
from pathlib import Path

from rtl_harness import lintoff


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=str(root), check=True, capture_output=True)


def _repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "ci@example.com")
    _git(tmp_path, "config", "user.name", "ci")
    (tmp_path / "rtl").mkdir()
    (tmp_path / "rtl" / "a.sv").write_text("module a;\nendmodule\n", encoding="utf-8")
    (tmp_path / "waivers.verible").write_text("# none\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "base")
    return tmp_path


def test_clean_tree_has_no_findings(tmp_path: Path):
    root = _repo(tmp_path)
    assert lintoff.scan(root) == []


def test_added_lint_off_is_found(tmp_path: Path):
    root = _repo(tmp_path)
    (root / "rtl" / "a.sv").write_text(
        "module a;\n// verilator lint_off WIDTH\nendmodule\n", encoding="utf-8"
    )
    found = lintoff.scan(root)
    assert len(found) == 1 and found[0]["file"] == "rtl/a.sv" and found[0]["line"] == 2
    assert "lint_off" in found[0]["text"]


def test_untracked_file_and_waiver_change(tmp_path: Path):
    root = _repo(tmp_path)
    (root / "rtl" / "b.sv").write_text(
        "module b; // verilog_lint: waive line-length\nendmodule\n", encoding="utf-8"
    )
    (root / "waivers.verible").write_text("waive --rule=line-length --line=1\n", encoding="utf-8")
    found = lintoff.scan(root)
    files = {f["file"] for f in found}
    assert files == {"rtl/b.sv", "waivers.verible"}
    assert lintoff.scan(root, include_untracked=False) and all(
        f["file"] == "waivers.verible" for f in lintoff.scan(root, include_untracked=False)
    )


def test_pr_range(tmp_path: Path):
    root = _repo(tmp_path)
    _git(root, "checkout", "-q", "-b", "feature")
    (root / "rtl" / "a.sv").write_text(
        "module a;\n/* verilator lint_off UNUSED */\nendmodule\n", encoding="utf-8"
    )
    _git(root, "commit", "-q", "-am", "suppress")
    assert lintoff.scan(root, "master...HEAD") or lintoff.scan(root, "main...HEAD")


def test_not_a_repo_is_empty(tmp_path: Path):
    (tmp_path / "x.sv").write_text("// verilator lint_off WIDTH\n")
    assert lintoff.scan(tmp_path) == []
