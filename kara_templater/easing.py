"""Pure easing functions for common state animations."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from itertools import pairwise
from typing import Self, overload

from .geometry import Vec2, _finite, finite
from .scene_animation import linear_rate


def ease_in(p: float) -> float:
    """An accelerating scalar easing curve for normalized progress."""
    return p * p


def ease_out(p: float) -> float:
    """A decelerating scalar easing curve for normalized progress."""
    return 1 - (1 - p) ** 2


def ease_in_out(p: float) -> float:
    """A scalar easing curve that accelerates then decelerates across normalized progress."""
    return 2 * p * p if p < 0.5 else 1 - 2 * (1 - p) ** 2


@overload
def there_and_back(
    p: float,
    *,
    peak_at: float = 0.5,
    return_at: float | None = None,
    rise: Callable[[float], float] = linear_rate,
    fall: Callable[[float], float] = linear_rate,
) -> float: ...


@overload
def there_and_back(
    p: None = None,
    *,
    peak_at: float = 0.5,
    return_at: float | None = None,
    rise: Callable[[float], float] = linear_rate,
    fall: Callable[[float], float] = linear_rate,
) -> BackRate: ...


def there_and_back(
    p: float | None = None,
    *,
    peak_at: float = 0.5,
    return_at: float | None = None,
    rise: Callable[[float], float] = linear_rate,
    fall: Callable[[float], float] = linear_rate,
) -> float | BackRate:
    """Use as a rate directly, or configure a peak, hold, rise and fall."""
    return_at = peak_at if return_at is None else return_at
    finite(peak_at)
    finite(return_at)
    if not 0 < peak_at <= return_at < 1:
        raise ValueError("require 0 < peak_at <= return_at < 1")
    if not callable(rise) or not callable(fall):
        raise TypeError("rise and fall must be rate functions")

    rate = BackRate(peak_at, return_at, rise, fall)
    return rate if p is None else rate(p)


@dataclass(frozen=True)
class BackRate:
    """Piecewise rise, hold and fall on normalized progress, independent of clocks."""

    peak_at: float
    return_at: float
    rise: Callable[[float], float]
    fall: Callable[[float], float]

    def __post_init__(self) -> None:
        finite(self.peak_at, self.return_at)
        if not 0 < self.peak_at <= self.return_at < 1:
            raise ValueError("require 0 < peak_at <= return_at < 1")
        if not callable(self.rise) or not callable(self.fall):
            raise TypeError("rise and fall must be rate functions")

    def __call__(self, progress: float) -> float:
        """Evaluate the configured rise, hold or fall without advancing state."""
        if progress < self.peak_at:
            return self.rise(progress / self.peak_at)
        if progress <= self.return_at:
            return 1.0
        return 1 - self.fall((progress - self.return_at) / (1 - self.return_at))


@dataclass(frozen=True)
class ProgressCurve:
    """Monotone piecewise linear (normalized time, progress) knots.

    Repeated progress values represent pauses. Repeated times are forbidden;
    instantaneous timing is represented by a zero-duration HighlightPass.
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

    @classmethod
    def cubic_bezier(cls, x1: float, y1: float, x2: float, y2: float) -> Self:
        """Approximate a normalized cubic Bézier with shared CPU and hook knots.

        The endpoints are (0, 0) and (1, 1). The x controls specify normalized
        time, and the y controls specify normalized progress. All controls
        must be finite and within 0..1. The piecewise-linear result differs from
        the Bézier by at most 0.0001 in progress at the same normalized time.
        """
        for value in (x1, y1, x2, y2):
            _finite(value, "Bézier control")
            if not 0 <= value <= 1:
                raise ValueError("Bézier controls must be within 0..1")

        tolerance = 0.0001
        knots = [(0.0, 0.0)]

        def subdivide(a: Vec2, b: Vec2, c: Vec2, d: Vec2) -> None:
            dx = d.x - a.x
            dy = d.y - a.y
            # The control polygon bounds the vertical error from the chord.
            error = max(abs((p.y - a.y) * dx - (p.x - a.x) * dy) for p in (b, c))
            if dy <= tolerance or error <= tolerance * dx:
                knots.append((d.x, d.y))
                return
            ab, bc, cd = a.lerp(b, 0.5), b.lerp(c, 0.5), c.lerp(d, 0.5)
            left, right = ab.lerp(bc, 0.5), bc.lerp(cd, 0.5)
            middle = left.lerp(right, 0.5)
            subdivide(a, ab, left, middle)
            subdivide(middle, right, cd, d)

        subdivide(Vec2(), Vec2(x1, y1), Vec2(x2, y2), Vec2(1, 1))
        return cls(tuple(knots))

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
