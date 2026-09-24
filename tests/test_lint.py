"""run_lint: output parsers, custom checks, severity map, and (when tools exist) the real thing."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rtl_harness import lint, rules
from rtl_harness.config import load_config
from rtl_harness.errors import ConfigError
from tests.conftest import HARNESS, requires_verible, requires_verilator

GOOD = (HARNESS / "tb" / "smoke" / "smoke_counter.sv").read_text(encoding="utf-8")

BAD = """// no timescale, wrong module name, async reset, TODO
module BadCounter (input logic clk, input logic rst, output logic [7:0] q);
    always @* q = q; // TODO fix
    always_ff @(posedge clk or negedge rst) begin
        if (rst) q <= 0; else q <= q + 1;
    end
endmodule
"""


# --- parsers ---------------------------------------------------------------------------------

def test_verible_regex():
    m = lint._VERIBLE_RX.match("rtl/a.sv:12:5: Use 'always_comb' instead of 'always @*'. [Style: combinational-logic] [always-comb]")
    assert m and m.group("rule") == "always-comb" and m.group("line") == "12"
    m = lint._VERIBLE_RX.match("rtl/a.sv:3:1-9: syntax error at token \"foo\"")
    assert m and m.group("rule") is None


def test_verilator_regex():
    m = lint._VERILATOR_RX.match("%Warning-WIDTHEXPAND: rtl/a.sv:10:22: Operator ADD expects 8 bits")
    assert m and m.group("code") == "WIDTHEXPAND" and m.group("file") == "rtl/a.sv" and m.group("line") == "10"
    m = lint._VERILATOR_RX.match("%Error: C:/proj/rtl/a.sv:3:1: syntax error, unexpected endmodule")
    assert m and m.group("kind") == "Error" and m.group("file") == "C:/proj/rtl/a.sv"
    m = lint._VERILATOR_RX.match("%Error: Cannot find file containing module: 'foo'")
    assert m and m.group("file") is None


# --- custom checks ---------------------------------------------------------------------------

def _checks(cfg):
    return {m.RULE: m for m in rules.load_checks(cfg)}


def test_custom_checks_on_good_and_bad(consumer: Path):
    cfg = load_config(consumer)
    checks = _checks(cfg)
    assert set(checks) >= {"timescale", "reset-style", "no-todo", "module-name-style"}
    for rule, mod in checks.items():
        assert mod.check(Path("smoke_counter.sv"), GOOD) == [], rule
    bad = Path("BadCounter.sv")
    assert checks["timescale"].check(bad, BAD)
    assert any("asynchronous" in f["message"] for f in checks["reset-style"].check(bad, BAD))
    assert checks["no-todo"].check(bad, BAD)
    assert checks["module-name-style"].check(bad, BAD)


def test_reset_style_rejects_active_high():
    text = "always_ff @(posedge clk) begin\n  if (rst) q <= 0;\nend\n"
    mod = _checks(load_config(HARNESS))["reset-style"]
    assert any("if (!rst_n)" in f["message"] for f in mod.check(Path("x.sv"), text))
    assert mod.check(Path("x.sv"), "always_ff @(posedge clk) begin\n  if (!sys_rst_n) q <= 0;\nend\n") == []


# --- severities ------------------------------------------------------------------------------

def test_severity_map_and_overrides(consumer: Path):
    cfg = load_config(consumer)
    sev = rules.load_severities(cfg)
    assert rules.severity_for(sev, "verible", "always-comb") == "error"
    assert rules.severity_for(sev, "verible", "unknown-rule") == "warning"
    assert rules.severity_for(sev, "verilator", "WIDTHEXPAND") == "error"
    assert rules.severity_for(sev, "verilator", "UNUSEDSIGNAL") == "warning"
    (consumer / "harness.toml").write_text(
        (consumer / "harness.toml").read_text() + '\n[lint]\nseverity_overrides = {"verible:explicit-begin" = "error"}\n'
    )
    cfg = load_config(consumer)
    assert rules.severity_for(rules.load_severities(cfg), "verible", "explicit-begin") == "error"


def test_override_cannot_lower(consumer: Path):
    (consumer / "harness.toml").write_text(
        (consumer / "harness.toml").read_text() + '\n[lint]\nseverity_overrides = {"verible:always-comb" = "warning"}\n'
    )
    with pytest.raises(ConfigError):
        rules.load_severities(load_config(consumer))


# --- the real pipeline -----------------------------------------------------------------------

@requires_verible
@requires_verilator
def test_run_lint_good_and_bad(consumer: Path):
    (consumer / "rtl" / "smoke_counter.sv").write_text(GOOD, encoding="utf-8", newline="\n")
    cfg = load_config(consumer)
    r = lint.run_lint(None, cfg=cfg)
    assert r["status"] == "pass", json.dumps(r, indent=1)
    assert r["lint"]["counts"]["error"] == 0
    assert (consumer / ".harness" / "last" / "lint.json").is_file()

    (consumer / "rtl" / "BadCounter.sv").write_text(BAD, encoding="utf-8", newline="\n")
    r = lint.run_lint(["rtl/BadCounter.sv"], cfg=load_config(consumer))
    assert r["status"] == "fail"
    rules_hit = {(f["tool"], f["rule"]) for f in r["lint"]["errors"]}
    assert ("custom", "timescale") in rules_hit
    assert ("custom", "no-todo") in rules_hit
    assert any(t == "verible" for t, _ in rules_hit)
    assert r["lint"]["counts"]["error"] >= 3


@requires_verible
def test_run_lint_rejects_outside_path(consumer: Path):
    from rtl_harness.errors import SafetyError

    with pytest.raises(SafetyError):
        lint.run_lint(["../outside.sv"], cfg=load_config(consumer))
