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
    """Protocol for pure path deformation at local seconds.

    Declare breakpoints and max_points before evaluation for deterministic sampling
    and preflight.
    """

    @property
    def max_points(self) -> int:
        """Declared path complexity bound used before sampling the geometry callback."""
        ...

    @property
    def breakpoints(self) -> tuple[float, ...]:
        """Object-local seconds at which deformation has a declared boundary."""
        ...

    def sample(self, base: VectorPath, time: float) -> VectorPath | None:
        """Evaluate path deformation at object-local seconds; return None for an empty path when supported."""
        ...


@dataclass(frozen=True)
class PathFunction:
    """Author callback receives seconds relative to the clock origin; None is invisible.

    Breakpoints may be negative local seconds; the owning object validates their
    absolute times. This supports visibility extended before an existing clock.
    """

    function: Callable[[VectorPath, float], VectorPath | None]
    max_points: int
    breakpoints: tuple[float, ...] = ()

    def __post_init__(self) -> None:
        if type(self.max_points) is not int or self.max_points < 1:
            raise ValueError(
                "geometry callbacks require a positive declared point bound"
            )
        finite(*self.breakpoints)

    def sample(self, base: VectorPath, time: float) -> VectorPath | None:
        """Evaluate the custom path callback at local seconds and enforce its declared point bound."""
        return self.function(base, time)


@dataclass(frozen=True)
class MorphPath:
    """Interpolate a path toward an explicitly corresponding target over local seconds.

    Contours and segment topology must match; shape correspondence is not inferred.
    """

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
        """Declared point bound of the corresponding source/target interpolation."""
        return self.target.point_count

    @property
    def breakpoints(self) -> tuple[float, ...]:
        """Local start and completion times used to split geometry sampling."""
        return (self.start, self.start + self.duration)

    def sample(self, base: VectorPath, time: float) -> VectorPath:
        """Evaluate corresponding path interpolation at local seconds, retaining endpoint geometry outside the morph interval."""
        progress = max(0, min(1, (time - self.start) / self.duration))
        return morph(base, self.target, self.rate(progress))


@dataclass(frozen=True)
class WritingStroke:
    """An authored contour with local start and positive duration in seconds.

    WritePath uses these stroke clocks for progressive reveal and lift gaps.
    """

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
        """The stroke contours flattened with the declared tolerance and point budget."""
        return tuple(
            flatten(s.path, tolerance=self.tolerance, max_points=self.max_points)
            for s in self.strokes
        )

    @property
    def breakpoints(self) -> tuple[float, ...]:
        """The local stroke boundaries and explicit lift gaps needed for reveal sampling."""
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
        """The complete stroked writing geometry after the final stroke finishes."""
        result = self._render(self.strokes[-1].start + self.strokes[-1].duration)
        assert result is not None
        return result

    def pen_down(self, time: float) -> bool:
        """Whether the authored writing schedule has an active stroke at local seconds."""
        finite(time)
        return any(s.start <= time < s.start + s.duration for s in self.strokes)

    def sample(self, base: VectorPath, time: float) -> VectorPath | None:
        """Return the revealed stroke geometry at local seconds, including completed stroke prefixes."""
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
