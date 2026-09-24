"""run_sim: build and run one registered cocotb block in the simulation interpreter and return
a SUMMARY only (docs/tool-schema.md). Details stay in the log and the waveform, which the
model fetches selectively through get_waveform.

The block's test file (test_<block>.py, found through harness.toml [sim].tests) is executed by
pytest under the sim python (.venv-sim on Windows). tb/harness_tb/runner_support prints marker
lines (RTL_HARNESS_RESULTS_XML=..., RTL_HARNESS_WAVES=...) that this module reads back.
"""

from __future__ import annotations

import json
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path

from . import paths
from ._proc import run
from ._safety import check_name, clean_env, rel
from .config import Config, load_config, test_files
from .errors import ToolMissing

_MARKER_RX = re.compile(r"^RTL_HARNESS_(RESULTS_XML|WAVES|BUILD_DIR)=(.+)$", re.MULTILINE)


def _parse_results(xml_path: Path) -> tuple[int, int, dict | None, list[dict]]:
    """(passed, failed, first_failure, tests) from a cocotb JUnit results.xml."""
    root = ET.parse(xml_path).getroot()
    passed = failed = 0
    first = None
    tests = []
    for tc in root.iter("testcase"):
        name = tc.get("name", "?")
        fail = tc.find("failure")
        if fail is None:
            fail = tc.find("error")
        sim_time = tc.get("sim_time_ns")
        entry = {"test": name, "status": "fail" if fail is not None else "pass", "time_s": float(tc.get("time", 0) or 0)}
        if sim_time is not None:
            entry["sim_time"] = {"value": float(sim_time), "unit": "ns"}
        tests.append(entry)
        if fail is not None:
            failed += 1
            if first is None:
                msg = (fail.get("message") or (fail.text or "").strip().splitlines()[-1:] or [""])
                msg = msg if isinstance(msg, str) else (msg[0] if msg else "")
                first = {"test": name, "message": msg[:500], "sim_time": entry.get("sim_time", {"value": 0, "unit": "ns"})}
        else:
            passed += 1
    return passed, failed, first, tests


def run_sim(block: str, *, waves: bool = False, timeout_s: float = 600.0, cfg: Config | None = None) -> dict:
    cfg = cfg or load_config()
    check_name(block, "block")
    tests = test_files(cfg)
    if block not in tests:
        known = ", ".join(sorted(tests)) or "(none found by [sim].tests)"
        raise ToolMissing(f"unknown block {block!r}; known blocks: {known}")
    test_path = tests[block]
    py = paths.sim_python()
    started = time.perf_counter()
    stamp = time.strftime("%Y%m%d_%H%M%S")
    log_dir = cfg.runtime / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{block}_{stamp}.log"

    env = clean_env({
        "RTL_HARNESS_CONSUMER": str(cfg.root),
        "RTL_HARNESS_BLOCK": block,
        "RTL_HARNESS_BUILD_DIR": str(cfg.root / cfg.build_dir),
        "COCOTB_WAVES": "1" if waves else "0",
        "PYTHONUNBUFFERED": "1",
    })
    # -s: the cocotb regression table and any CHECK FAILED lines flow into the log.
    args = [py, "-m", "pytest", str(test_path), "-s", "-v", "-p", "no:cacheprovider", "--rootdir", str(test_path.parent)]
    r = run(args, cwd=cfg.root, env=env, timeout_s=timeout_s)
    log_path.write_text(r.stdout + "\n" + r.stderr, encoding="utf-8")

    markers = {k: v.strip() for k, v in _MARKER_RX.findall(r.stdout)}
    results_xml = Path(markers["RESULTS_XML"]) if markers.get("RESULTS_XML") else None
    waveform = markers.get("WAVES") or None

    passed = failed = 0
    first = None
    tests_detail: list[dict] = []
    if results_xml and results_xml.is_file():
        try:
            passed, failed, first, tests_detail = _parse_results(results_xml)
        except ET.ParseError:
            pass

    if r.timed_out:
        status = "timeout"
    elif results_xml is None or not results_xml.is_file():
        status = "build_error"
    elif failed or not r.ok:
        status = "fail"
    else:
        status = "pass"
    if status in ("build_error", "timeout") and first is None:
        tail = [ln for ln in (r.stderr + r.stdout).splitlines() if ln.strip()][-1:]
        first = {"test": "", "message": (tail[0] if tail else status)[:500], "sim_time": {"value": 0, "unit": "ns"}}

    result = {
        "status": status,
        "passed": passed,
        "failed": failed,
        "first_failure": first,
        "tests": tests_detail,
        "log_path": rel(cfg.root, log_path),
        "waveform_path": (rel(cfg.root, Path(waveform)) if waveform and Path(waveform).exists() else None),
        "duration_s": round(time.perf_counter() - started, 3),
        "source": {"block": block, "test_file": rel(cfg.root, test_path), "engine": cfg.engine, "seed": 1, "waves": waves, "returncode": r.returncode},
    }
    _save_last(cfg, "sim", result)
    return result


def run_all(*, waves: bool = False, timeout_s: float = 600.0, cfg: Config | None = None) -> dict:
    cfg = cfg or load_config()
    blocks = []
    for block in sorted(test_files(cfg)):
        blocks.append(run_sim(block, waves=waves, timeout_s=timeout_s, cfg=cfg))
    failed = sum(b["status"] != "pass" for b in blocks)
    result = {"status": "pass" if blocks and not failed else ("fail" if blocks else "no_blocks"), "blocks": blocks, "failed_blocks": failed}
    _save_last(cfg, "sim_all", result)
    return result


def _save_last(cfg: Config, name: str, result: dict) -> None:
    try:
        d = cfg.runtime / "last"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{name}.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
