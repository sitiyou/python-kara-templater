"""Renderer-independent singing timelines. Coordinates never include decoration.

All intervals use absolute milliseconds and untransformed script coordinates.
Evaluation keeps sub-millisecond precision; ASS quantization belongs to output.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from itertools import pairwise
from math import isfinite
from typing import Self

from .model import LaidOutLine


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
        return self.right - self.left

    @property
    def center(self) -> float:
        return (self.left + self.right) / 2

    def at(self, progress: float) -> float:
        return self.left + self.width * progress


@dataclass(frozen=True)
class ProgressCurve:
    """Monotone piecewise linear (normalized time, progress) knots.

    Repeated progress values represent pauses. Repeated times are forbidden;
    instantaneous singing is represented by a zero-duration SingingPass.
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
        if not 0 < time_fraction < 1 or not 0 < progress_fraction < 1:
            raise ValueError("stage fractions must be strictly within 0..1")
        return cls(((0, 0), (time_fraction, progress_fraction), (1, 1)))

    def at(self, time_fraction: float) -> float:
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


@dataclass(frozen=True)
class SingingPass:
    """One traversal of a body region, optionally part of an explicit repeat round."""

    start_ms: int
    end_ms: int
    region: Region
    curve: ProgressCurve = ProgressCurve()
    round_id: int = 0

    def __post_init__(self) -> None:
        _milliseconds(self.start_ms, "singing start")
        _milliseconds(self.end_ms, "singing end")
        if self.end_ms < self.start_ms:
            raise ValueError("singing pass is reversed")
        if type(self.round_id) is not int or self.round_id < 0:
            raise ValueError("round_id must be a nonnegative integer")

    def progress_at(self, time_ms: float) -> float:
        _finite(time_ms, "time")
        if time_ms < self.start_ms:
            return 0.0
        if time_ms >= self.end_ms:
            return 1.0
        return self.curve.at((time_ms - self.start_ms) / (self.end_ms - self.start_ms))

    def position_at(self, time_ms: float) -> float:
        return self.region.at(self.progress_at(time_ms))

    def arrival(self, x: float) -> float | None:
        _finite(x, "position")
        if not self.region.width or not self.region.left <= x <= self.region.right:
            return None
        fraction = self.curve.arrival((x - self.region.left) / self.region.width)
        return self.start_ms + (self.end_ms - self.start_ms) * fraction


@dataclass(frozen=True)
class EdgeSweep:
    padding_px: float = 0
    lead_ms: int = 0
    tail_ms: int = 0

    def __post_init__(self) -> None:
        _finite(self.padding_px, "padding")
        if self.padding_px < 0:
            raise ValueError("padding cannot be negative")
        _milliseconds(self.lead_ms, "lead")
        _milliseconds(self.tail_ms, "tail")

    def position_at(self, singing: SingingPass, paint: Region, time_ms: float) -> float:
        """Decorative front only; never feed this result into singing triggers.

        The paint extent may be re-evaluated for dynamic effects each frame.
        It must enclose the timing region. Padding expands that safe extent.
        """
        _finite(time_ms, "time")
        body = singing.region
        if paint.left > body.left or paint.right < body.right:
            raise ValueError("paint region must enclose timing region")
        left, right = paint.left - self.padding_px, paint.right + self.padding_px
        if time_ms < singing.start_ms:
            p = (
                max(0, 1 - (singing.start_ms - time_ms) / self.lead_ms)
                if self.lead_ms
                else 0
            )
            return left + (body.left - left) * p
        if time_ms < singing.end_ms:
            return singing.position_at(time_ms)
        p = min(1, (time_ms - singing.end_ms) / self.tail_ms) if self.tail_ms else 1
        return body.right + (right - body.right) * p


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


@dataclass(frozen=True)
class HighlightTrack:
    id: str
    unit_index: int
    passes: tuple[SingingPass, ...]
    repeat: str = "hold"
    end_behavior: str = "hold"

    def __post_init__(self) -> None:
        object.__setattr__(self, "passes", tuple(self.passes))
        if not isinstance(self.id, str) or not self.id:
            raise ValueError("track needs a stable nonempty id")
        if type(self.unit_index) is not int or self.unit_index < 0:
            raise ValueError("unit_index must be a nonnegative integer")
        if not self.passes:
            raise ValueError(f"track {self.id}: at least one singing pass is required")
        if self.repeat not in {"hold", "reset"} or self.end_behavior not in {
            "hold",
            "hide",
        }:
            raise ValueError(f"track {self.id}: invalid lifecycle policy")
        for previous, current in pairwise(self.passes):
            if previous.end_ms > current.start_ms:
                raise ValueError(
                    f"track {self.id}: overlapping or reversed passes; use separate tracks"
                )
            if current.round_id < previous.round_id:
                raise ValueError(f"track {self.id}: rounds must not reverse")
        for index, current in enumerate(self.passes):
            for previous in self.passes[:index]:
                overlap = min(previous.region.right, current.region.right) - max(
                    previous.region.left, current.region.left
                )
                if previous.round_id == current.round_id and overlap > 0:
                    raise ValueError(
                        f"track {self.id}: repeated region requires a new round_id"
                    )

    def regions_at(self, time_ms: float) -> tuple[Region, ...]:
        _finite(time_ms, "time")
        if self.end_behavior == "hide" and time_ms >= self.passes[-1].end_ms:
            return ()
        started = [p for p in self.passes if time_ms >= p.start_ms]
        if self.repeat == "reset" and started:
            started = [p for p in started if p.round_id == started[-1].round_id]
        return union_regions(
            Region(p.region.left, p.position_at(time_ms)) for p in started
        )


def tracks_from_layout(layout: LaidOutLine) -> tuple[HighlightTrack, ...]:
    """Use layout's ruby-weighted partitions as explicitly approximate body regions.

    Static units have no track. Empty-reading partitions retain their duration
    without contributing spatial coverage. Custom/repeated mappings use passes
    supplied by the caller instead.
    """
    return tuple(
        HighlightTrack(
            f"unit:{i}",
            i,
            tuple(
                SingingPass(s.source.start_ms, s.source.end_ms, Region(s.left, s.right))
                for s in unit.segments
            ),
        )
        for i, unit in enumerate(layout.units)
        if unit.segments
    )
