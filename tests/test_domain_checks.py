"""Domain checks (rules/bus, rules/cpu) fire on the textbook mistakes and stay quiet on the
examples."""

from __future__ import annotations

from pathlib import Path

from rtl_harness import rules
from rtl_harness.config import load_config
from tests.conftest import HARNESS


def _checks(domains: list[str]):
    cfg = load_config(HARNESS)
    cfg.domains = domains
    return {m.RULE: m for m in rules.load_checks(cfg)}


def test_bus_checks_on_snippets():
    c = _checks(["bus"])
    assert {"valid-depends-on-ready", "combinational-ready-path"} <= set(c)
    bad = "assign m_valid = s_valid && m_ready;\nassign s_ready = m_ready;\n"
    assert c["valid-depends-on-ready"].check(Path("x.sv"), bad)
    assert c["combinational-ready-path"].check(Path("x.sv"), bad)
    good = "assign s_ready = !skid_valid;\nassign m_valid = out_valid;\n"
    assert not c["valid-depends-on-ready"].check(Path("x.sv"), good)
    assert not c["combinational-ready-path"].check(Path("x.sv"), good)


def test_cpu_unique_case_on_snippets():
    c = _checks(["cpu"])
    assert "unique-case" in c
    bad = "always_comb begin\n    case (op)\n        default: y = 0;\n    endcase\nend\n"
    good = "always_comb begin\n    unique case (op)\n        default: y = 0;\n    endcase\nend\nalways_ff @(posedge clk) begin\n    case (s)\n default: q <= 0;\n    endcase\nend\n"
    assert c["unique-case"].check(Path("x.sv"), bad)
    assert not c["unique-case"].check(Path("x.sv"), good)


def test_examples_are_clean_for_every_domain_check():
    c = _checks(["bus", "cpu", "verif"])
    for sv in sorted((HARNESS / "examples").rglob("*.sv")):
        text = sv.read_text(encoding="utf-8")
        for rule, mod in c.items():
            assert mod.check(sv, text) == [], f"{sv.name}: {rule}"


def test_domain_severities_merge():
    cfg = load_config(HARNESS)
    sev = rules.load_severities(cfg)
    assert rules.severity_for(sev, "custom", "valid-depends-on-ready") == "error"
    assert rules.severity_for(sev, "custom", "combinational-ready-path") == "warning"
    assert rules.severity_for(sev, "custom", "unique-case") == "warning"
