"""Subprocess helper: argument lists only (never a shell), mandatory timeout, capped output."""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from ._safety import clip


@dataclass
class Result:
    args: list[str]
    returncode: int
    stdout: str
    stderr: str
    duration_s: float
    timed_out: bool = False
    clipped: bool = False

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out


def run(
    args: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    timeout_s: float,
    stdin_text: str | None = None,
) -> Result:
    start = time.perf_counter()
    try:
        proc = subprocess.run(
            [str(a) for a in args],
            cwd=str(cwd),
            env=env,
            input=stdin_text,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_s,
            shell=False,
        )
        out, c1 = clip(proc.stdout or "")
        err, c2 = clip(proc.stderr or "")
        return Result(
            [str(a) for a in args],
            proc.returncode,
            out,
            err,
            time.perf_counter() - start,
            False,
            c1 or c2,
        )
    except subprocess.TimeoutExpired as exc:
        out, _ = clip(
            (exc.stdout or b"").decode("utf-8", "replace")
            if isinstance(exc.stdout, bytes)
            else (exc.stdout or "")
        )
        err, _ = clip(
            (exc.stderr or b"").decode("utf-8", "replace")
            if isinstance(exc.stderr, bytes)
            else (exc.stderr or "")
        )
        return Result(
            [str(a) for a in args],
            -1,
            out,
            err + f"\n[timeout after {timeout_s}s]\n",
            time.perf_counter() - start,
            True,
            True,
        )
    except FileNotFoundError as exc:
        return Result(
            [str(a) for a in args],
            127,
            "",
            f"executable not found: {exc}",
            time.perf_counter() - start,
        )
