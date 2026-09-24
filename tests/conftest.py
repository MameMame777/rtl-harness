"""Shared fixtures: a throw-away consumer project with its own harness.toml."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from rtl_harness import paths

HARNESS = paths.harness_root()

MINIMAL_TOML = """
[harness]
schema = 1
[design]
sources = ["rtl/**/*.sv"]
[domains]
active = []
[sim]
tests = ["tb/**/test_*.py"]
"""


@pytest.fixture
def consumer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A scratch project root selected through RTL_HARNESS_CONSUMER."""
    (tmp_path / "harness.toml").write_text(MINIMAL_TOML, encoding="utf-8")
    (tmp_path / "rtl").mkdir()
    (tmp_path / "tb").mkdir()
    monkeypatch.setenv("RTL_HARNESS_CONSUMER", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    return tmp_path


def have_tool(name: str, subdir: str) -> bool:
    return paths.find_tool(name, subdir) is not None


def have_verilator() -> bool:
    try:
        paths.verilator()
        return True
    except Exception:
        return False


requires_verible = pytest.mark.skipif(
    not have_tool("verible-verilog-lint", "verible"), reason="verible not installed"
)
requires_verilator = pytest.mark.skipif(not have_verilator(), reason="verilator not found")
requires_sim = pytest.mark.skipif(
    not (
        have_verilator()
        and (
            os.environ.get("RTL_HARNESS_SIM_PYTHON")
            or (HARNESS / ".venv-sim").exists()
            or os.name != "nt"
        )
    ),
    reason="simulation environment not set up",
)
