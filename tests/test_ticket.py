"""ticket: local records, redaction, list/close, and the escalation preview (no network)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rtl_harness import ticket
from rtl_harness.config import load_config
from rtl_harness.errors import HarnessError


def test_redact_defaults_and_custom():
    text = r"see E:\Users\me\proj\x.sv and /home/me/x and me@corp.example.com at 203.0.113.9 (ACME-INTERNAL)"  # hygiene-ok: redaction fixture
    out = ticket.redact(text, [r"ACME-INTERNAL"])
    assert "Users" not in out and "/home/" not in out and "@" not in out and "203.0" not in out and "ACME" not in out
    assert out.count("<redacted>") == 5


def test_new_list_close_locally(consumer: Path):
    cfg = load_config(consumer)
    (consumer / ".harness" / "last").mkdir(parents=True)
    (consumer / ".harness" / "last" / "lint.json").write_text(json.dumps({
        "status": "fail", "lint": {"errors": [{"file": "rtl/a.sv", "line": 3, "severity": "error", "tool": "custom", "rule": "timescale", "message": "no timescale"}], "counts": {"error": 1, "warning": 0}},
        "source": {"files": ["rtl/a.sv"]}}))
    r = ticket.new(cfg, kind="deviation", domain="bus", title="AI dropped the timescale", model="claude",
                   attach_last=True, notes=r"prompt mentioned C:\secret\path", submit=False)  # hygiene-ok: redaction fixture
    assert r["issue"] is None
    path = consumer / r["path"]
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\nid: ") and "kind: deviation" in text and "status: open" in text
    assert "no timescale" in text and "rtl/a.sv" in text
    assert "secret" not in text and "<redacted>" in text  # absolute path redacted

    rows = ticket.list_tickets(cfg)
    assert len(rows) == 1 and rows[0]["id"] == r["id"] and rows[0]["title"] == "AI dropped the timescale"
    r2 = ticket.new(cfg, kind="bug", domain="cpu", title="second", submit=False)
    assert r2["id"].endswith("-002")
    ticket.close(cfg, r["id"])
    assert [t["status"] for t in ticket.list_tickets(cfg)] == ["closed", "open"]


def test_validation(consumer: Path):
    cfg = load_config(consumer)
    with pytest.raises(HarnessError):
        ticket.new(cfg, kind="nope", domain="bus", title="x", submit=False)
    with pytest.raises(HarnessError):
        ticket.new(cfg, kind="bug", domain="bus", title="   ", submit=False)
    with pytest.raises(HarnessError):
        ticket.close(cfg, "20000101-999")


def test_escalate_preview_without_yes(consumer: Path):
    (consumer / "harness.toml").write_text((consumer / "harness.toml").read_text() + '\n[tickets]\nescalate_repo = "acme/rtl-harness"\n')
    cfg = load_config(consumer)
    r = ticket.new(cfg, kind="tool", domain="verif", title="run_sim timeout", notes="took 1000s", submit=False)
    p = ticket.escalate(cfg, r["id"], yes=False)
    assert p["submitted"] is False and p["repo"] == "acme/rtl-harness" and "took 1000s" in p["preview"]
    bug = ticket.new(cfg, kind="bug", domain="bus", title="local only", submit=False)
    with pytest.raises(HarnessError):
        ticket.escalate(cfg, bug["id"], yes=False)
