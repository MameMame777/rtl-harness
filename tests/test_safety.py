"""Input validation: paths stay inside the project, names are identifiers, env is filtered."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from rtl_harness import _safety
from rtl_harness.errors import SafetyError


def test_within_accepts_inside(tmp_path: Path):
    f = tmp_path / "rtl" / "a.sv"
    f.parent.mkdir()
    f.write_text("x")
    assert _safety.within(tmp_path, "rtl/a.sv") == f.resolve()
    assert _safety.within(tmp_path, f) == f.resolve()
    assert _safety.within(tmp_path, ".") == tmp_path.resolve()


@pytest.mark.parametrize(
    "bad",
    [
        "../x.sv",
        "rtl/../../x.sv",
        "/etc/passwd",
        # a drive-letter path is absolute only on Windows; elsewhere it is a relative name
        pytest.param(
            "C:/Windows/system.ini",
            marks=pytest.mark.skipif(os.name != "nt", reason="windows path"),
        ),
    ],
)
def test_within_rejects_outside(tmp_path: Path, bad: str):
    with pytest.raises(SafetyError):
        _safety.within(tmp_path, bad)


def test_within_rejects_symlink_escape(tmp_path: Path):
    outside = tmp_path.parent / f"{tmp_path.name}_outside"
    outside.mkdir(exist_ok=True)
    (outside / "secret.sv").write_text("x")
    link = tmp_path / "link"
    try:
        os.symlink(outside, link, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not permitted here")
    with pytest.raises(SafetyError):
        _safety.within(tmp_path, "link/secret.sv")


def test_safe_glob_filters_suffix_exclude_and_escape(tmp_path: Path):
    (tmp_path / "rtl").mkdir()
    (tmp_path / "rtl" / "a.sv").write_text("x")
    (tmp_path / "rtl" / "b.txt").write_text("x")
    (tmp_path / "rtl" / "vendor").mkdir()
    (tmp_path / "rtl" / "vendor" / "c.sv").write_text("x")
    got = _safety.safe_glob(tmp_path, ["rtl/**/*.sv"], ["rtl/vendor/**"])
    assert [p.name for p in got] == ["a.sv"]
    with pytest.raises(SafetyError):
        _safety.safe_glob(tmp_path, ["../**/*.sv"])


@pytest.mark.parametrize("name", ["smoke_counter", "axi4lite_regs", "Block-1.v2"])
def test_check_name_ok(name: str):
    assert _safety.check_name(name) == name


@pytest.mark.parametrize("name", ["../x", "a;rm -rf", "a b", "", "$(x)", "x" * 81, "-lead"])
def test_check_name_rejects(name: str):
    with pytest.raises(SafetyError):
        _safety.check_name(name)


def test_clean_env_filters(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SUPER_SECRET_TOKEN", "abc")
    monkeypatch.setenv("COCOTB_SEED", "1")
    env = _safety.clean_env({"VERILATOR_ROOT": "/x"}, path_prepend="/tools")
    assert "SUPER_SECRET_TOKEN" not in env
    assert env["COCOTB_SEED"] == "1"
    assert env["VERILATOR_ROOT"] == "/x"
    assert env["PATH"].startswith("/tools")


def test_clip():
    text, clipped = _safety.clip("a" * 10, limit=4)
    assert clipped and text.startswith("aaaa")
    assert _safety.clip("ok") == ("ok", False)
