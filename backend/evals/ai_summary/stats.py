"""Stdlib-only statistics for the eval report (protocol §5)."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

Z_95 = 1.959963984540054
NOT_TESTABLE = "not testable at this n"
# Exact two-sided McNemar cannot reach p < 0.05 below 6 discordant pairs.
MIN_DISCORDANT = 6


def wilson(k: int, n: int, z: float = Z_95) -> tuple[float, float]:
    """95% Wilson score interval for k successes out of n."""
    if n <= 0 or k < 0 or k > n:
        raise ValueError(f"invalid counts k={k} n={n}")
    p = k / n
    z2 = z * z
    denom = 1 + z2 / n
    centre = (p + z2 / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / denom
    return max(0.0, centre - margin), min(1.0, centre + margin)


@dataclass(frozen=True)
class McNemarResult:
    b: int
    c: int
    testable: bool
    p_value: float | None
    note: str = ""


def mcnemar_exact(b: int, c: int) -> McNemarResult:
    """Exact two-sided McNemar test on discordant counts b (fixed) and c (broke)."""
    if b < 0 or c < 0:
        raise ValueError("discordant counts must be non-negative")
    n = b + c
    if n < MIN_DISCORDANT:
        return McNemarResult(b=b, c=c, testable=False, p_value=None, note=NOT_TESTABLE)
    tail = sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2**n
    return McNemarResult(b=b, c=c, testable=True, p_value=min(1.0, 2 * tail))


@dataclass
class Flips:
    fixed: list[str] = field(default_factory=list)
    broke: list[str] = field(default_factory=list)
    unchanged_pass: list[str] = field(default_factory=list)
    unchanged_fail: list[str] = field(default_factory=list)

    @property
    def b(self) -> int:
        return len(self.fixed)

    @property
    def c(self) -> int:
        return len(self.broke)


def flips(before: dict[str, bool], after: dict[str, bool]) -> Flips:
    """Per-case paired outcomes (True = pass) between two runs on the same cases."""
    if set(before) != set(after):
        raise ValueError("flips needs the same cases in both runs")
    result = Flips()
    for case_id in sorted(before):
        was, now = before[case_id], after[case_id]
        if not was and now:
            result.fixed.append(case_id)
        elif was and not now:
            result.broke.append(case_id)
        elif now:
            result.unchanged_pass.append(case_id)
        else:
            result.unchanged_fail.append(case_id)
    return result
