"""Bounded nonzero-fill path booleans using a planar horizontal sweep."""

from collections import defaultdict
from dataclasses import dataclass
from math import atan2
from typing import Literal

from .geometry import Contour, Vec2, VectorPath, finite
from .path_geometry import GeometryError, flatten

type PathBooleanOperation = Literal["intersection", "union", "difference", "xor"]


@dataclass
class _Work:
    limit: int
    used: int = 0

    def charge(self, amount: int) -> None:
        self.used += amount
        if self.used > self.limit:
            raise GeometryError("path boolean work budget exceeded")


@dataclass(frozen=True)
class _Edge:
    a: Vec2
    b: Vec2
    operand: int

    @property
    def delta(self) -> int:
        return 1 if self.b.y > self.a.y else -1

    def x(self, y: float) -> float:
        return self.a.x + (self.b.x - self.a.x) * (
            (y - self.a.y) / (self.b.y - self.a.y)
        )


def _cross(a: Vec2, b: Vec2) -> float:
    return a.x * b.y - a.y * b.x


def _point(x: float, y: float) -> Vec2:
    # Canonicalize shared vertices far below ASS drawing serialization precision.
    return Vec2(round(x, 9), round(y, 9))


def _inside(a: int, b: int, operation: PathBooleanOperation) -> bool:
    if operation == "intersection":
        return bool(a and b)
    if operation == "union":
        return bool(a or b)
    if operation == "difference":
        return bool(a and not b)
    return bool(a) != bool(b)


def _simplify(points: list[Vec2], work: _Work) -> list[Vec2]:
    while len(points) >= 3:
        work.charge(len(points))
        result: list[Vec2] = []
        for index, b in enumerate(points):
            a, c = points[index - 1], points[(index + 1) % len(points)]
            ac, ab, bc = c - a, b - a, c - b
            if (
                ac.length
                and abs(_cross(ac, ab)) <= ac.length * 1e-8
                and ab.x * bc.x + ab.y * bc.y >= 0
            ):
                continue
            result.append(b)
        if len(result) == len(points):
            return result
        points = result
    return []


def _contours(
    segments: list[tuple[Vec2, Vec2]], max_points: int, work: _Work
) -> VectorPath | None:
    # Opposite copies cancel; no internal strip edge survives to be stroked.
    net: dict[tuple[Vec2, Vec2], int] = defaultdict(int)
    for a, b in segments:
        if a == b:
            continue
        if (a.x, a.y) < (b.x, b.y):
            net[a, b] += 1
        else:
            net[b, a] -= 1
    edges = [(a, b) if count > 0 else (b, a) for (a, b), count in net.items() if count]
    outgoing: dict[Vec2, list[int]] = defaultdict(list)
    for index, (a, _) in enumerate(edges):
        outgoing[a].append(index)
    unused = set(range(len(edges)))
    result: list[Contour] = []
    total = 0
    while unused:
        index = min(unused)
        start = edges[index][0]
        loop = [start]
        while True:
            work.charge(1)
            unused.remove(index)
            a, b = edges[index]
            if b == start:
                break
            loop.append(b)
            choices = [candidate for candidate in outgoing[b] if candidate in unused]
            if not choices:
                raise GeometryError(
                    "path boolean boundary cannot be stitched at numeric precision"
                )
            direction = b - a

            def turn(candidate: int, b: Vec2 = b, direction: Vec2 = direction) -> float:
                following = edges[candidate][1] - b
                return atan2(
                    _cross(direction, following),
                    direction.x * following.x + direction.y * following.y,
                )

            # Filled area is on the right. At a point contact, keep its contour
            # separate by taking the rightmost continuation of the incoming edge.
            index = max(choices, key=turn)
        loop = _simplify(loop, work)
        if len(loop) < 3:
            continue
        area = sum(
            _cross(a - loop[0], b - loop[0])
            for a, b in zip(loop, (*loop[1:], loop[0]), strict=True)
        )
        if area == 0:
            continue
        total += len(loop)
        if total > max_points:
            raise GeometryError("path boolean result point budget exceeded")
        result.extend(VectorPath.polygon(*loop).contours)
    return VectorPath(tuple(result)) if result else None


def path_boolean(
    first: VectorPath,
    second: VectorPath,
    operation: PathBooleanOperation = "intersection",
    *,
    tolerance: float = 0.25,
    max_points: int = 4096,
    max_work: int = 1_000_000,
) -> VectorPath | None:
    """Boolean closed filled paths under nonzero winding, including holes.

    Curves flatten with the declared local tolerance. Polygon crossings split
    the sweep into exact linear strips; shared vertices canonicalize at 1e-9
    path units and collinear cleanup uses 1e-8. Output is stitched into actual
    exterior/hole contours, so stroking does not reveal internal sweep strips.
    max_points bounds combined flattened input and final output; scratch edges
    are limited to 8*max_points. max_work bounds pair tests and sweep work.
    None denotes empty area. Open contours are rejected.
    """
    finite(tolerance)
    if operation not in ("intersection", "union", "difference", "xor"):
        raise ValueError("unknown path boolean operation")
    if (
        tolerance <= 0
        or type(max_points) is not int
        or max_points < 3
        or type(max_work) is not int
        or max_work < 1
    ):
        raise ValueError(
            "path booleans need positive tolerance/work and max_points >= 3"
        )
    if first.point_count + second.point_count > max_points:
        raise GeometryError("path boolean input point budget exceeded")
    work = _Work(max_work)
    edges: list[_Edge] = []
    levels: set[float] = set()
    count = 0
    for operand, path in enumerate((first, second)):
        for contour in path.contours:
            if not contour.closed:
                raise GeometryError("path booleans require closed contours")
            points = flatten(contour, tolerance=tolerance, max_points=max_points).points
            count += len(points) - int(points[0] == points[-1])
            if count > max_points:
                raise GeometryError(
                    "path boolean flattened input point budget exceeded"
                )
            levels.update(point.y for point in points)
            edges.extend(
                _Edge(a, b, operand)
                for a, b in zip(points, points[1:], strict=False)
                if a.y != b.y
            )
    work.charge(len(edges) * (len(edges) - 1) // 2)
    for index, edge in enumerate(edges):
        r = edge.b - edge.a
        for other in edges[index + 1 :]:
            s = other.b - other.a
            denominator = _cross(r, s)
            finite(denominator)
            if denominator == 0:
                continue
            offset = other.a - edge.a
            t, u = _cross(offset, s) / denominator, _cross(offset, r) / denominator
            if 0 < t < 1 and 0 < u < 1:
                levels.add(edge.a.y + t * r.y)
    ordered = sorted(levels)
    sides: list[tuple[Vec2, Vec2]] = []
    horizontal: dict[float, list[tuple[float, int]]] = defaultdict(list)
    scratch = 0
    for top, bottom in zip(ordered, ordered[1:], strict=False):
        work.charge(len(edges))
        middle = (top + bottom) / 2
        if not top < middle < bottom:
            continue
        active = sorted(
            (edge.x(middle), index)
            for index, edge in enumerate(edges)
            if min(edge.a.y, edge.b.y) < middle < max(edge.a.y, edge.b.y)
        )
        winding = [0, 0]
        left: _Edge | None = None
        index = 0
        while index < len(active):
            work.charge(1)
            x, identity = active[index]
            before = _inside(*winding, operation)
            while index < len(active) and abs(active[index][0] - x) <= 1e-9:
                edge = edges[active[index][1]]
                winding[edge.operand] += edge.delta
                index += 1
            after = _inside(*winding, operation)
            if not before and after:
                left = edges[identity]
            elif before and not after:
                assert left is not None
                right = edges[identity]
                lt, rt = _point(left.x(top), top), _point(right.x(top), top)
                lb, rb = _point(left.x(bottom), bottom), _point(right.x(bottom), bottom)
                sides.extend(((rt, rb), (lb, lt)))
                horizontal[lt.y].extend(((lt.x, 1), (rt.x, -1)))
                horizontal[lb.y].extend(((lb.x, -1), (rb.x, 1)))
                scratch += 6
                if scratch > max_points * 8:
                    raise GeometryError(
                        "path boolean intermediate point budget exceeded"
                    )
                left = None
        if _inside(*winding, operation):
            raise GeometryError("path boolean has an unbalanced winding boundary")
    for y, events in horizontal.items():
        work.charge(len(events))
        changes: dict[float, int] = defaultdict(int)
        for x, delta in events:
            changes[x] += delta
        winding = 0
        start = 0.0
        for x, delta in sorted(changes.items()):
            previous = winding
            winding += delta
            if previous and (not winding or (previous > 0) != (winding > 0)):
                a, b = Vec2(start, y), Vec2(x, y)
                sides.append((a, b) if previous > 0 else (b, a))
            if winding and (not previous or (previous > 0) != (winding > 0)):
                start = x
    return _contours(sides, max_points, work)
