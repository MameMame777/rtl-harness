"""CLI wiring: commands parse, exit codes follow the contract, JSON output is JSON."""

from __future__ import annotations

import json
from pathlib import Path

from rtl_harness.cli import main


def test_doctor_json(capsys, consumer: Path):
    rc = main(["doctor", "--json"])
    out = json.loads(capsys.readouterr().out)
    assert rc in (0, 1) and out["consumer_root"] == str(consumer)


def test_provision_dry_run_and_apply(capsys, consumer: Path):
    assert main(["provision", "--check"]) == 1
    assert main(["provision"]) == 0
    assert main(["provision", "--check"]) == 0


def test_ticket_and_sync_stub(capsys, consumer: Path):
    assert main(["ticket", "new", "--kind", "bug", "--domain", "cpu", "--title", "cli ticket", "--no-submit"]) == 0
    assert main(["ticket", "list"]) == 0
    assert "cli ticket" in capsys.readouterr().out
    assert main(["sync", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "unimplemented"
    assert main(["wave"]) == 2


def test_lintoff_cli_outside_git(capsys, consumer: Path):
    assert main(["lintoff", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == []
