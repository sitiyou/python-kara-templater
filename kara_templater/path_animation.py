"""Seekable geometry animations with declared bounds and discontinuities."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import cached_property
from typing import Protocol

from .geometry import Contour, Vec2, VectorPath, finite
from .path_geometry import GeometryError, Polyline, flatten, morph, stroke
from .scene_animation import linear_rate


class GeometryAnimation(Protocol):
    @property
    def max_points(self) -> int: ...
    @property
    def breakpoints(self) -> tuple[float, ...]: ...
    def sample(self, base: VectorPath, time: float) -> VectorPath | None: ...


@dataclass(frozen=True)
class PathFunction:
    """Author callback receives seconds relative to object birth; None is invisible."""

    function: Callable[[VectorPath, float], VectorPath | None]
    max_points: int
    breakpoints: tuple[float, ...] = ()

    def __post_init__(self) -> None:
        if type(self.max_points) is not int or self.max_points < 1:
            raise ValueError(
                "geometry callbacks require a positive declared point bound"
            )
        finite(*self.breakpoints)
        if any(t < 0 for t in self.breakpoints):
            raise ValueError("geometry breakpoints must be nonnegative")

    def sample(self, base: VectorPath, time: float) -> VectorPath | None:
        return self.function(base, time)


@dataclass(frozen=True)
class MorphPath:
    target: VectorPath
    start: float = 0
    duration: float = 1
    rate: Callable[[float], float] = linear_rate

    def __post_init__(self) -> None:
        finite(self.start, self.duration)
        if self.start < 0 or self.duration <= 0:
            raise ValueError("morph needs a nonnegative start and positive duration")

    @property
    def max_points(self) -> int:
        return self.target.point_count

    @property
    def breakpoints(self) -> tuple[float, ...]:
        return (self.start, self.start + self.duration)

    def sample(self, base: VectorPath, time: float) -> VectorPath:
        progress = max(0, min(1, (time - self.start) / self.duration))
        return morph(base, self.target, self.rate(progress))


@dataclass(frozen=True)
class WritingStroke:
    path: Contour
    start: float
    duration: float

    def __post_init__(self) -> None:
        finite(self.start, self.duration)
        if self.start < 0 or self.duration <= 0:
            raise ValueError("stroke needs a nonnegative start and positive duration")
        if self.path.closed:
            raise ValueError("writing strokes must be explicit open paths")


@dataclass(frozen=True)
class WritePath:
    """Ordered, author-supplied strokes. Font outlines do not imply writing order."""

    strokes: tuple[WritingStroke, ...]
    width: float = 4
    tolerance: float = 0.25
    max_points: int = 4096

    def __post_init__(self) -> None:
        finite(self.width, self.tolerance)
        if not self.strokes or min(self.width, self.tolerance) <= 0:
            raise ValueError("writing needs strokes and positive width/tolerance")
        if type(self.max_points) is not int or self.max_points < 4:
            raise ValueError("writing point bound must be an integer >= 4")
        if any(
            a.start + a.duration > b.start
            for a, b in zip(self.strokes, self.strokes[1:], strict=False)
        ):
            raise ValueError("ordered writing strokes cannot overlap")
        count = 0
        for line in self.lines:
            if line.length == 0:
                raise GeometryError("writing stroke has zero length")
            count += 4 * len(line.points) - 4
        if count > self.max_points:
            raise GeometryError("writing geometry exceeds declared point bound")

    @cached_property
    def lines(self) -> tuple[Polyline, ...]:
        return tuple(
            flatten(s.path, tolerance=self.tolerance, max_points=self.max_points)
            for s in self.strokes
        )

    @property
    def breakpoints(self) -> tuple[float, ...]:
        return tuple(t for s in self.strokes for t in (s.start, s.start + s.duration))

    def tip(self, time: float) -> Vec2:
        """During a pen-up pause, hold at the preceding stroke's endpoint."""
        finite(time)
        point = self.lines[0].points[0]
        for spec, line in zip(self.strokes, self.lines, strict=True):
            if time < spec.start:
                break
            point = line.point((time - spec.start) / spec.duration)
        return point

    @cached_property
    def full_path(self) -> VectorPath:
        result = self._render(self.strokes[-1].start + self.strokes[-1].duration)
        assert result is not None
        return result

    def pen_down(self, time: float) -> bool:
        finite(time)
        return any(s.start <= time < s.start + s.duration for s in self.strokes)

    def sample(self, base: VectorPath, time: float) -> VectorPath | None:
        return self._render(time)

    def _render(self, time: float) -> VectorPath | None:
        contours: list[Contour] = []
        for spec, line in zip(self.strokes, self.lines, strict=True):
            if time <= spec.start:
                break
            drawn = stroke(
                line.prefix((time - spec.start) / spec.duration),
                self.width,
                max_points=self.max_points,
            )
            if drawn is not None:
                contours.extend(drawn.contours)
        return VectorPath(tuple(contours)) if contours else None
