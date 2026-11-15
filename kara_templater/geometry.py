"""Immutable geometry shared by scene objects, layouts and procedural effects."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from math import cos, hypot, isfinite, radians, sin


def finite(*values: float) -> None:
    if not all(isfinite(value) for value in values):
        raise ValueError("geometry and animation values must be finite")


@dataclass(frozen=True)
class Vec2:
    x: float = 0
    y: float = 0

    def __post_init__(self) -> None:
        finite(self.x, self.y)

    def __add__(self, other: Vec2) -> Vec2:
        return Vec2(self.x + other.x, self.y + other.y)

    def __sub__(self, other: Vec2) -> Vec2:
        return Vec2(self.x - other.x, self.y - other.y)

    def __mul__(self, factor: float) -> Vec2:
        return Vec2(self.x * factor, self.y * factor)

    def lerp(self, other: Vec2, progress: float) -> Vec2:
        return self + (other - self) * progress

    @property
    def length(self) -> float:
        return hypot(self.x, self.y)

    def rotated(self, degrees: float) -> Vec2:
        """Positive angles rotate clockwise in screen coordinates."""
        angle = radians(degrees)
        return Vec2(
            self.x * cos(angle) - self.y * sin(angle),
            self.x * sin(angle) + self.y * cos(angle),
        )


@dataclass(frozen=True)
class Affine2D:
    """Screen-coordinate affine map; ``outer @ inner`` applies inner first."""

    a: float = 1
    b: float = 0
    c: float = 0
    d: float = 1
    tx: float = 0
    ty: float = 0

    def __post_init__(self) -> None:
        finite(self.a, self.b, self.c, self.d, self.tx, self.ty)

    def apply(self, point: Vec2) -> Vec2:
        return Vec2(
            self.a * point.x + self.c * point.y + self.tx,
            self.b * point.x + self.d * point.y + self.ty,
        )

    def __matmul__(self, other: Affine2D) -> Affine2D:
        return Affine2D(
            self.a * other.a + self.c * other.b,
            self.b * other.a + self.d * other.b,
            self.a * other.c + self.c * other.d,
            self.b * other.c + self.d * other.d,
            self.a * other.tx + self.c * other.ty + self.tx,
            self.b * other.tx + self.d * other.ty + self.ty,
        )


@dataclass(frozen=True)
class LineSegment:
    end: Vec2

    def point(self, start: Vec2, progress: float) -> Vec2:
        return start.lerp(self.end, progress)


@dataclass(frozen=True)
class CubicSegment:
    control1: Vec2
    control2: Vec2
    end: Vec2

    def point(self, start: Vec2, progress: float) -> Vec2:
        u = 1 - progress
        return (
            start * (u**3)
            + self.control1 * (3 * u * u * progress)
            + self.control2 * (3 * u * progress * progress)
            + self.end * (progress**3)
        )


type Segment2D = LineSegment | CubicSegment


@dataclass(frozen=True)
class Contour:
    start: Vec2
    segments: tuple[Segment2D, ...]
    closed: bool = True

    def __post_init__(self) -> None:
        if not self.segments:
            raise ValueError("a contour requires at least one segment")

    def point(self, progress: float) -> Vec2:
        """Parameter-uniform sampling, not an arc-length claim."""
        finite(progress)
        segments = self.segments
        if self.closed and segments[-1].end != self.start:
            segments = (*segments, LineSegment(self.start))
        value = min(1, max(0, progress)) * len(segments)
        index = min(int(value), len(segments) - 1)
        start = self.start if index == 0 else segments[index - 1].end
        return segments[index].point(start, value - index)


@dataclass(frozen=True)
class VectorPath:
    contours: tuple[Contour, ...]

    def __post_init__(self) -> None:
        if not self.contours:
            raise ValueError("a path requires at least one contour")

    @classmethod
    def polygon(cls, *points: Vec2) -> VectorPath:
        if len(points) < 3:
            raise ValueError("a polygon requires at least three vertices")
        return cls((Contour(points[0], tuple(LineSegment(p) for p in points[1:])),))

    @classmethod
    def rectangle(cls, width: float, height: float) -> VectorPath:
        finite(width, height)
        if width <= 0 or height <= 0:
            raise ValueError("rectangle dimensions must be positive")
        return cls.polygon(Vec2(), Vec2(width, 0), Vec2(width, height), Vec2(0, height))

    @classmethod
    def circle(cls, radius: float) -> VectorPath:
        """Four cubic arcs, centered at the origin (the usual circle approximation)."""
        finite(radius)
        if radius <= 0:
            raise ValueError("circle radius must be positive")
        k = radius * 0.5522847498307936
        r = radius
        return cls(
            (
                Contour(
                    Vec2(r, 0),
                    (
                        CubicSegment(Vec2(r, k), Vec2(k, r), Vec2(0, r)),
                        CubicSegment(Vec2(-k, r), Vec2(-r, k), Vec2(-r, 0)),
                        CubicSegment(Vec2(-r, -k), Vec2(-k, -r), Vec2(0, -r)),
                        CubicSegment(Vec2(k, -r), Vec2(r, -k), Vec2(r, 0)),
                    ),
                ),
            )
        )

    def map(self, transform: Callable[[Vec2], Vec2]) -> VectorPath:
        def segment(value: Segment2D) -> Segment2D:
            if isinstance(value, LineSegment):
                return LineSegment(transform(value.end))
            return CubicSegment(
                transform(value.control1),
                transform(value.control2),
                transform(value.end),
            )

        return VectorPath(
            tuple(
                Contour(
                    transform(c.start), tuple(segment(s) for s in c.segments), c.closed
                )
                for c in self.contours
            )
        )

    @property
    def point_count(self) -> int:
        return sum(
            1 + sum(1 if isinstance(s, LineSegment) else 3 for s in c.segments)
            for c in self.contours
        )

    def drawing(self) -> str:
        """Standard ASS p1 path, preserving winding and all contours."""

        def point(value: Vec2) -> str:
            return f"{value.x:.4f} {value.y:.4f}"

        parts: list[str] = []
        for contour in self.contours:
            parts.append("m " + point(contour.start))
            for segment in contour.segments:
                if isinstance(segment, LineSegment):
                    parts.append("l " + point(segment.end))
                else:
                    parts.append(
                        "b "
                        + " ".join(
                            point(p)
                            for p in (segment.control1, segment.control2, segment.end)
                        )
                    )
            if contour.closed:
                parts.append("l " + point(contour.start))
        return " ".join(parts)
