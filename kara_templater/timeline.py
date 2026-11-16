"""Display windows, horizontal regions and normalized progress curves.

Only DisplayWindow uses milliseconds; progress curves are dimensionless.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from itertools import pairwise
from math import isfinite
from typing import Self


def _finite(value, name):
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not isfinite(value)
    ):
        raise ValueError(f"{name} must be finite")


def _milliseconds(value, name) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be nonnegative integer milliseconds")
    return value


@dataclass(frozen=True)
class DisplayWindow:
    """An absolute millisecond visibility interval independent of source singing time.

    Animation padding changes this window rather than lyric segment clocks.
    """

    start_ms: int
    end_ms: int

    def __post_init__(self) -> None:
        _milliseconds(self.start_ms, "display start")
        _milliseconds(self.end_ms, "display end")
        if self.end_ms <= self.start_ms:
            raise ValueError("display window must have positive duration")


@dataclass(frozen=True)
class Region:
    """A horizontal interval in script pixels; an empty interval is valid."""

    left: float
    right: float

    def __post_init__(self) -> None:
        _finite(self.left, "left")
        _finite(self.right, "right")
        if self.right < self.left:
            raise ValueError("region is reversed")

    @property
    def width(self) -> float:
        """The horizontal region extent in script pixels."""
        return self.right - self.left

    @property
    def center(self) -> float:
        """The midpoint of the horizontal region."""
        return (self.left + self.right) / 2

    def at(self, progress: float) -> float:
        """Interpolate a position across the region using normalized progress."""
        return self.left + self.width * progress


@dataclass(frozen=True)
class ProgressCurve:
    """Monotone piecewise linear (normalized time, progress) knots.

    Repeated progress values represent pauses. Repeated times are forbidden;
    instantaneous singing is represented by a zero-duration HighlightPass.
    """

    knots: tuple[tuple[float, float], ...] = ((0, 0), (1, 1))

    def __post_init__(self) -> None:
        object.__setattr__(self, "knots", tuple(tuple(k) for k in self.knots))
        if len(self.knots) < 2 or self.knots[0] != (0, 0) or self.knots[-1] != (1, 1):
            raise ValueError("curve must run from (0, 0) to (1, 1)")
        for knot in self.knots:
            if len(knot) != 2:
                raise ValueError("curve knots must be (time, progress) pairs")
            for value in knot:
                _finite(value, "curve coordinate")
                if not 0 <= value <= 1:
                    raise ValueError("curve coordinates must be within 0..1")
        for (t0, p0), (t1, p1) in pairwise(self.knots):
            if t1 <= t0 or p1 < p0:
                raise ValueError(
                    "curve times must increase and progress cannot reverse"
                )

    @classmethod
    def two_stage(cls, *, time_fraction: float, progress_fraction: float) -> Self:
        """Construct a piecewise-linear progress curve through one explicit time/progress breakpoint."""
        if not 0 < time_fraction < 1 or not 0 < progress_fraction < 1:
            raise ValueError("stage fractions must be strictly within 0..1")
        return cls(((0, 0), (time_fraction, progress_fraction), (1, 1)))

    def at(self, time_fraction: float) -> float:
        """Evaluate normalized sweep progress from this piecewise-linear curve."""
        _finite(time_fraction, "time fraction")
        t = min(1, max(0, time_fraction))
        for (t0, p0), (t1, p1) in pairwise(self.knots):
            if t <= t1:
                return p0 + (p1 - p0) * (t - t0) / (t1 - t0)
        return 1.0

    def arrival(self, progress: float) -> float:
        """Earliest normalized time reaching progress, including plateau starts."""
        _finite(progress, "progress")
        if not 0 <= progress <= 1:
            raise ValueError("progress must be within 0..1")
        if progress == 0:
            return 0.0
        for (t0, p0), (t1, p1) in pairwise(self.knots):
            if p0 < progress <= p1:
                return t0 + (t1 - t0) * (progress - p0) / (p1 - p0)
        raise AssertionError("validated curve must reach every progress value")


def union_regions(regions: Iterable[Region]) -> tuple[Region, ...]:
    """Merge coverage without filling gaps or painting overlaps twice."""
    result = []
    for region in sorted(regions, key=lambda r: (r.left, r.right)):
        if not region.width:
            continue
        if result and region.left <= result[-1].right:
            result[-1] = Region(result[-1].left, max(result[-1].right, region.right))
        else:
            result.append(region)
    return tuple(result)
