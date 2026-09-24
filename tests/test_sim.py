"""run_sim: results parsing (offline) and the real smoke block (when the sim env exists)."""

from __future__ import annotations

from pathlib import Path

import pytest

from rtl_harness import config as _config
from rtl_harness import sim
from rtl_harness.config import load_config
from rtl_harness.errors import SafetyError, ToolMissing
from tests.conftest import HARNESS, requires_sim

SAMPLE_XML = """<?xml version="1.0"?>
<testsuites>
  <testsuite name="all" package="all">
    <testcase classname="test_x" name="alpha" file="x.py" lineno="1" time="0.10" sim_time_ns="100.0"/>
    <testcase classname="test_x" name="beta" file="x.py" lineno="2" time="0.20" sim_time_ns="250.0">
      <failure message="CHECK FAILED: beat 4 (got 7, expected 8)"/>
    </testcase>
  </testsuite>
</testsuites>
"""


def test_parse_results(tmp_path: Path):
    xml = tmp_path / "results.xml"
    xml.write_text(SAMPLE_XML, encoding="utf-8")
    passed, failed, first, tests = sim._parse_results(xml)
    assert (passed, failed) == (1, 1)
    assert first["test"] == "beta" and "CHECK FAILED" in first["message"]
    assert first["sim_time"] == {"value": 250.0, "unit": "ns"}
    assert [t["status"] for t in tests] == ["pass", "fail"]


def test_marker_regex():
    text = "junk\nRTL_HARNESS_BUILD_DIR=C:/x/.harness/build/b\nRTL_HARNESS_RESULTS_XML=/p/results.xml\n"
    got = dict(sim._MARKER_RX.findall(text))
    assert got["RESULTS_XML"] == "/p/results.xml" and got["BUILD_DIR"].endswith("build/b")


def test_unknown_block_and_bad_name(consumer: Path):
    cfg = load_config(consumer)
    with pytest.raises(ToolMissing):
        sim.run_sim("nope", cfg=cfg)
    with pytest.raises(SafetyError):
        sim.run_sim("../evil", cfg=cfg)


def test_smoke_block_is_discovered():
    assert "smoke_counter" in _config.test_files(load_config(HARNESS))


@requires_sim
def test_run_sim_smoke_counter(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("RTL_HARNESS_CONSUMER", str(HARNESS))
    r = sim.run_sim("smoke_counter", cfg=load_config(HARNESS))
    assert r["status"] == "pass", r
    assert r["passed"] >= 2 and r["failed"] == 0
    assert r["first_failure"] is None
    assert (HARNESS / r["log_path"]).is_file()
    assert (HARNESS / ".harness" / "last" / "sim.json").is_file()
