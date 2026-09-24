"""Pass/fail helpers. check(cond, msg) raises AssertionError("CHECK FAILED: ...") so the same
token shows up in every log; a test passes by returning normally."""

from __future__ import annotations

from typing import Any


def check(cond: Any, msg: str) -> None:
    if not cond:
        raise AssertionError(f"CHECK FAILED: {msg}")


def check_eq(got: Any, exp: Any, msg: str) -> None:
    if got != exp:
        raise AssertionError(f"CHECK FAILED: {msg} (got {got!r}, expected {exp!r})")


class Scoreboard:
    """Ordered expected-vs-observed compare."""

    def __init__(self, name: str = "scoreboard") -> None:
        self.name = name
        self.expected: list[Any] = []
        self.actual: list[Any] = []

    def expect(self, item: Any) -> None:
        self.expected.append(item)

    def observe(self, item: Any) -> None:
        self.actual.append(item)

    @property
    def matched(self) -> int:
        return sum(1 for e, a in zip(self.expected, self.actual, strict=False) if e == a)

    def check(self) -> None:
        check_eq(len(self.actual), len(self.expected), f"{self.name}: item count")
        for i, (exp, got) in enumerate(zip(self.expected, self.actual, strict=False)):
            check_eq(got, exp, f"{self.name}[{i}]")
