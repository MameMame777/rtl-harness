"""Deterministic valid-gap / backpressure injection for handshake-robustness stress.

Drivers feed continuous valid (1 beat/clk) by default. Injecting random idle cycles between
beats -- and random `ready` backpressure on the sink -- reaches the bugs where a design advances
state on the raw clock instead of on an accepted beat. The golden output is a function of the
ACCEPTED-beat sequence only, so scoreboards need no change: a mismatch under gaps is a real bug.

Off by default (COCOTB_GAP unset -> kind "none" -> next_gap() is 0). Seeded from COCOTB_SEED
(pinned to 1 by runner_support) so a stress run is reproducible.

Env: COCOTB_GAP = none | sparse | burst | adversarial (default none); COCOTB_GAP_MAX (default 3).
"""

from __future__ import annotations

import os
import random
from collections import Counter

KINDS = ("none", "sparse", "burst", "adversarial")


class GapPolicy:
    """Yields the number of idle cycles to insert before each accepted beat."""

    def __init__(
        self, kind: str = "none", seed: int = 1, max_gap: int = 3, prob: float = 0.5
    ) -> None:
        if kind not in KINDS:
            raise ValueError(f"gap kind {kind!r}: choose from {KINDS}")
        self.kind = kind
        self.max_gap = max(0, int(max_gap))
        self.prob = prob
        self.rng = random.Random(seed)
        self.produced: Counter = Counter()

    @property
    def active(self) -> bool:
        return self.kind != "none" and self.max_gap > 0

    def next_gap(self) -> int:
        if not self.active:
            g = 0
        elif self.kind == "sparse":
            g = self.rng.randint(1, self.max_gap) if self.rng.random() < self.prob else 0
        elif self.kind == "burst":
            g = self.rng.randint(0, self.max_gap)
        else:  # adversarial
            g = self.rng.randint(1, self.max_gap)
        self.produced[g] += 1
        return g


def _seed() -> int:
    try:
        return int(os.environ.get("COCOTB_SEED", "1"), 0)
    except ValueError:
        return 1


def make_gap_policy(kind: str | None = None, max_gap: int | None = None) -> GapPolicy:
    """A fresh policy from the arguments, else from COCOTB_GAP / COCOTB_GAP_MAX / COCOTB_SEED."""
    if max_gap is None:
        try:
            max_gap = int(os.environ.get("COCOTB_GAP_MAX", "3"), 0)
        except ValueError:
            max_gap = 3
    return GapPolicy(
        kind=(kind or os.environ.get("COCOTB_GAP", "none")).lower(), seed=_seed(), max_gap=max_gap
    )


_DEFAULT: GapPolicy | None = None


def default_gap_policy() -> GapPolicy:
    """Process-wide default, built once from the environment and shared by the drivers."""
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = make_gap_policy()
    return _DEFAULT
