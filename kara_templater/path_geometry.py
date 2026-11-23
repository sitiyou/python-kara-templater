"""Bounded curve subdivision, length queries, strokes and explicit morphing."""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from functools import cached_property, lru_cache
from math import hypot

from .geometry import (
    Contour,
    CubicSegment,
    LineSegment,
    Segment2D,
    Vec2,
    VectorPath,
    finite,
)
from .model import Box


class GeometryError(ValueError):
    """A geometric operation cannot satisfy its declared topology or budget."""


def _point_budget(value: int) -> None:
    if type(value) is not int or value < 2:
        raise ValueError("geometry point budget must be an integer >= 2")


@dataclass(frozen=True)
class Polyline:
    """A finite sequence of points supporting cumulative distance, interpolation, prefixes, and resampling.

    It is the explicit flattened representation used by path algorithms.
    """

    points: tuple[Vec2, ...]

    def __post_init__(self) -> None:
        if not self.points:
            raise ValueError("polyline requires a point")

    @cached_property
    def distances(self) -> tuple[float, ...]:
        """Cumulative flattened distance at every point, starting from zero."""
        values: list[float] = [0.0]
        for a, b in zip(self.points, self.points[1:], strict=False):
            values.append(values[-1] + (b - a).length)
        return tuple(values)

    @property
    def length(self) -> float:
        """The total cumulative length of the flattened point sequence."""
        return self.distances[-1]

    def point(self, progress: float) -> Vec2:
        """Return the point at normalized distance along the polyline."""
        finite(progress)
        distance = min(1, max(0, progress)) * self.length
        index = bisect_right(self.distances, distance)
        if index >= len(self.points):
            return self.points[-1]
        a, b = self.distances[index - 1], self.distances[index]
        return self.points[index - 1].lerp(self.points[index], (distance - a) / (b - a))

    def prefix(self, progress: float) -> Polyline:
        """Return the polyline prefix through a normalized distance, including its interpolated final point."""
        finite(progress)
        progress = min(1, max(0, progress))
        if progress == 1:
            return self
        stop = bisect_right(self.distances, progress * self.length)
        values = (*self.points[:stop], self.point(progress))
        return Polyline(
            tuple(p for i, p in enumerate(values) if i == 0 or p != values[i - 1])
        )

    def slice(self, start: float, end: float) -> Polyline:
        """Return a normalized arc-length interval, clamped to the path ends.

        Reversed intervals raise ValueError; an empty interval contains one point.
        Interpolated endpoints retain interior vertices without resampling.
        """
        finite(start, end)
        if start > end:
            raise ValueError("polyline interval is reversed")
        start, end = max(0, min(1, start)), max(0, min(1, end))
        values = (
            self.point(start),
            *(point for point, distance in zip(self.points, self.distances, strict=True)
              if start * self.length < distance < end * self.length),
            self.point(end),
        )
        return Polyline(tuple(p for i, p in enumerate(values) if i == 0 or p != values[i - 1]))

    def resample(self, count: int) -> Polyline:
        """Return evenly spaced samples along the flattened path distance."""
        _point_budget(count)
        return Polyline(tuple(self.point(i / (count - 1)) for i in range(count)))

    @property
    def signed_area(self) -> float:
        """Compute the signed polygon area of this point sequence."""
        return (
            sum(
                a.x * b.y - b.x * a.y
                for a, b in zip(
                    self.points, (*self.points[1:], self.points[0]), strict=True
                )
            )
            / 2
        )


def flatten(
    contour: Contour, *, tolerance: float = 0.25, max_points: int = 4096
) -> Polyline:
    """Adaptive de Casteljau subdivision; tolerance is in local path units.

    Flatness bounds the control polygon's distance to its chord. This is not
    an arc-length error bound, and later object scaling magnifies the distance.
    """
    finite(tolerance)
    _point_budget(max_points)
    if tolerance <= 0:
        raise ValueError("curve tolerance must be positive")
    result = [contour.start]

    def emit(point: Vec2) -> None:
        if point != result[-1]:
            if len(result) >= max_points:
                raise GeometryError("curve subdivision point budget exceeded")
            result.append(point)

    def distance(point: Vec2, a: Vec2, b: Vec2) -> float:
        dx, dy = b.x - a.x, b.y - a.y
        px, py = point.x - a.x, point.y - a.y
        length2 = dx * dx + dy * dy
        if not length2:
            return hypot(px, py)
        t = max(0, min(1, (px * dx + py * dy) / length2))
        return hypot(px - t * dx, py - t * dy)

    def cubic(a: Vec2, b: Vec2, c: Vec2, d: Vec2, depth: int) -> None:
        if max(distance(b, a, d), distance(c, a, d)) <= tolerance:
            emit(d)
            return
        if depth >= 32:
            raise GeometryError("curve subdivision recursion budget exceeded")
        ab, bc, cd = a.lerp(b, 0.5), b.lerp(c, 0.5), c.lerp(d, 0.5)
        abc, bcd = ab.lerp(bc, 0.5), bc.lerp(cd, 0.5)
        middle = abc.lerp(bcd, 0.5)
        cubic(a, ab, abc, middle, depth + 1)
        cubic(middle, bcd, cd, d, depth + 1)

    start = contour.start
    for segment in contour.segments:
        if isinstance(segment, LineSegment):
            emit(segment.end)
        else:
            cubic(start, segment.control1, segment.control2, segment.end, 0)
        start = segment.end
    if contour.closed:
        emit(contour.start)
    return Polyline(tuple(result))


def stroke(
    line: Polyline, width: float, *, max_points: int = 4096
) -> VectorPath | None:
    """Fill an open polyline with bevel joins and butt caps; empty length is invisible."""
    finite(width)
    _point_budget(max_points)
    if width <= 0:
        raise ValueError("stroke width must be positive")
    points = tuple(
        p for i, p in enumerate(line.points) if i == 0 or p != line.points[i - 1]
    )
    if len(points) < 2:
        return None
    if 4 * len(points) - 4 > max_points:
        raise GeometryError("stroke outline point budget exceeded")
    normals = tuple(
        Vec2(-(b - a).y, (b - a).x) * (width / (2 * (b - a).length))
        for a, b in zip(points, points[1:], strict=False)
    )
    left, right = [points[0] + normals[0]], [points[0] - normals[0]]
    for index, point in enumerate(points[1:-1], 1):
        left.extend((point + normals[index - 1], point + normals[index]))
        right.extend((point - normals[index - 1], point - normals[index]))
    left.append(points[-1] + normals[-1])
    right.append(points[-1] - normals[-1])
    return VectorPath.polygon(*left, *reversed(right))


def resample_path(
    path: VectorPath,
    points_per_contour: int,
    *,
    tolerance: float = 0.25,
    max_points: int = 4096,
) -> VectorPath:
    """Explicit correspondence preparation; contour order and winding are retained."""
    _point_budget(points_per_contour)
    if points_per_contour < 3 and any(c.closed for c in path.contours):
        raise ValueError("closed contours need at least three samples")
    _point_budget(max_points)
    if len(path.contours) * points_per_contour > max_points:
        raise GeometryError("resampling point budget exceeded")
    contours: list[Contour] = []
    for contour in path.contours:
        count = points_per_contour + int(contour.closed)
        points = (
            flatten(contour, tolerance=tolerance, max_points=max_points)
            .resample(count)
            .points
        )
        if contour.closed:
            points = points[:-1]
        contours.append(
            Contour(
                points[0], tuple(LineSegment(p) for p in points[1:]), contour.closed
            )
        )
    return VectorPath(tuple(contours))


@lru_cache(maxsize=128)
def _match(source: VectorPath, target: VectorPath) -> None:
    if len(source.contours) != len(target.contours):
        raise GeometryError(
            "morph contour count differs; provide explicit matching shapes"
        )
    for index, (a, b) in enumerate(zip(source.contours, target.contours, strict=True)):
        if a.closed != b.closed or len(a.segments) != len(b.segments):
            raise GeometryError(
                f"morph contour {index}: closure or segment count differs; resample explicitly"
            )
        if any(
            type(x) is not type(y) for x, y in zip(a.segments, b.segments, strict=True)
        ):
            raise GeometryError(f"morph contour {index}: segment orders differ")
        if a.closed:
            area_a, area_b = flatten(a).signed_area, flatten(b).signed_area
            if abs(area_a) < 1e-9 or abs(area_b) < 1e-9 or area_a * area_b <= 0:
                raise GeometryError(
                    f"morph contour {index}: degenerate contour or winding mismatch (hole/outer correspondence)"
                )


def morph(source: VectorPath, target: VectorPath, progress: float) -> VectorPath:
    """Interpolate explicitly paired contours and vertices, including hole winding.

    This is not automatic glyph matching. Even valid endpoint correspondence can
    self-intersect between endpoints; authors must preview their chosen mapping.
    """
    finite(progress)
    _match(source, target)

    def segment(a: Segment2D, b: Segment2D) -> Segment2D:
        if isinstance(a, LineSegment) and isinstance(b, LineSegment):
            return LineSegment(a.end.lerp(b.end, progress))
        assert isinstance(a, CubicSegment) and isinstance(b, CubicSegment)
        return CubicSegment(
            a.control1.lerp(b.control1, progress),
            a.control2.lerp(b.control2, progress),
            a.end.lerp(b.end, progress),
        )

    return VectorPath(
        tuple(
            Contour(
                a.start.lerp(b.start, progress),
                tuple(
                    segment(x, y) for x, y in zip(a.segments, b.segments, strict=True)
                ),
                a.closed,
            )
            for a, b in zip(source.contours, target.contours, strict=True)
        )
    )


def intersect_convex(
    path: VectorPath,
    boundary: tuple[Vec2, ...],
    *,
    tolerance: float = 0.25,
    max_points: int = 4096,
) -> VectorPath | None:
    """Intersect filled contours with a convex polygon, retaining hole winding.

    Curves are flattened explicitly. This is a bounded intersection operation,
    not a general union/difference engine for arbitrary self-intersecting paths.
    """
    _point_budget(max_points)
    if len(boundary) < 3 or len(boundary) > max_points:
        raise GeometryError("clip polygon needs 3..max_points vertices")

    def cross(a: Vec2, b: Vec2) -> float:
        return a.x * b.y - a.y * b.x

    area = Polyline(boundary).signed_area
    if abs(area) < 1e-9:
        raise GeometryError("clip polygon is degenerate")
    direction = 1 if area > 0 else -1
    edges = tuple(zip(boundary, (*boundary[1:], boundary[0]), strict=True))
    for a, b in edges:
        if a == b or any(direction * cross(b - a, p - a) < -1e-9 for p in boundary):
            raise GeometryError("clip boundary must be a simple convex polygon")
    contours: list[Contour] = []
    count = 0
    for contour in path.contours:
        if not contour.closed:
            raise GeometryError("filled intersection requires closed contours")
        polygon = list(
            flatten(contour, tolerance=tolerance, max_points=max_points).points
        )
        if polygon[0] == polygon[-1]:
            polygon.pop()
        for a, b in edges:
            if not polygon:
                break
            output: list[Vec2] = []
            previous = polygon[-1]
            previous_side = direction * cross(b - a, previous - a)
            for current in polygon:
                side = direction * cross(b - a, current - a)
                inside, was_inside = side >= -1e-9, previous_side >= -1e-9
                if inside != was_inside:
                    output.append(
                        previous.lerp(current, previous_side / (previous_side - side))
                    )
                if inside:
                    output.append(current)
                if len(output) > max_points:
                    raise GeometryError(
                        "intersection intermediate point budget exceeded"
                    )
                previous, previous_side = current, side
            polygon = output
        unique = tuple(
            p for i, p in enumerate(polygon) if i == 0 or p != polygon[i - 1]
        )
        if len(unique) >= 3 and abs(Polyline(unique).signed_area) > 1e-9:
            count += len(unique)
            if count > max_points:
                raise GeometryError("intersection result point budget exceeded")
            contours.extend(VectorPath.polygon(*unique).contours)
    return VectorPath(tuple(contours)) if contours else None


def path_bounds(path: VectorPath) -> Box:
    """Conservative control-point bounds, before appearance and transforms."""
    points: list[Vec2] = []
    for contour in path.contours:
        points.append(contour.start)
        for segment in contour.segments:
            if isinstance(segment, CubicSegment):
                points.extend((segment.control1, segment.control2))
            points.append(segment.end)
    left, top = min(p.x for p in points), min(p.y for p in points)
    return Box(
        left, top, max(p.x for p in points) - left, max(p.y for p in points) - top
    )
