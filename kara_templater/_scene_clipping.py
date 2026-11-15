"""Bounded world-space resolution and intersection of inherited scene masks."""

from collections import OrderedDict
from dataclasses import dataclass, replace
from typing import Literal

from .geometry import Vec2, VectorPath
from .path_boolean import path_boolean
from .path_geometry import Polyline, flatten, intersect_convex
from .scene import RectangleClip, SceneObject, VectorClip
from .scene_animation import VisualState, local_seconds
from .scene_evaluation import SceneEvaluator
from .sources import EventOrigin

type ResolvedClip = RectangleClip | VectorClip | None | Literal[False]


class SceneClipError(ValueError):
    def __init__(
        self, message: str, *, object_id: str, origin: EventOrigin | None
    ) -> None:
        super().__init__(message)
        self.object_id = object_id
        self.origin = origin


@dataclass(frozen=True)
class ResolvedMasks:
    clip: ResolvedClip
    peak_points: int = 0


def _points(clip: ResolvedClip) -> int:
    return clip.path.point_count if isinstance(clip, VectorClip) else 4 if clip else 0


def _path(clip: RectangleClip | VectorClip) -> VectorPath:
    if isinstance(clip, VectorClip):
        return clip.path
    # Screen rectangle clipping uses ASS integer coordinates.
    left, top, right, bottom = (
        round(v) for v in (clip.left, clip.top, clip.right, clip.bottom)
    )
    return VectorPath.polygon(
        Vec2(left, top), Vec2(right, top), Vec2(right, bottom), Vec2(left, bottom)
    )


def rectangle_difference(
    region: RectangleClip, hole: RectangleClip
) -> tuple[RectangleClip, ...]:
    """Disjoint integer rectangles preserve native hard clip boundaries."""
    left, top, right, bottom = (
        round(v) for v in (region.left, region.top, region.right, region.bottom)
    )
    x0, y0 = max(left, round(hole.left)), max(top, round(hole.top))
    x1, y1 = min(right, round(hole.right)), min(bottom, round(hole.bottom))
    if x0 >= x1 or y0 >= y1:
        return (region,)
    return tuple(
        RectangleClip(a, b, c, d)
        for a, b, c, d in (
            (left, top, right, y0),
            (left, y1, right, bottom),
            (left, y0, x0, y1),
            (x1, y0, right, y1),
        )
        if a < c and b < d
    )


def _convex(path: VectorPath, max_points: int) -> tuple[Vec2, ...] | None:
    if len(path.contours) != 1 or not path.contours[0].closed:
        return None
    points = flatten(path.contours[0], tolerance=0.25, max_points=max_points).points
    if points[0] == points[-1]:
        points = points[:-1]
    if len(points) < 3:
        return None
    area = Polyline(points).signed_area
    if abs(area) < 1e-9:
        return None
    sign = 1 if area > 0 else -1
    for a, b in zip(points, (*points[1:], points[0]), strict=True):
        if a == b or any(
            sign * ((b.x - a.x) * (p.y - a.y) - (b.y - a.y) * (p.x - a.x)) < -1e-9
            for p in points
        ):
            return None
    return points


def _intersection(
    first: RectangleClip | VectorClip,
    second: RectangleClip | VectorClip,
    max_points: int,
    max_work: int,
) -> ResolvedClip:
    if first == second:
        return first
    if first.inverse or second.inverse:
        a, b = _path(first), _path(second)
        if first.inverse and second.inverse:
            result = path_boolean(
                a, b, "union", max_points=max_points, max_work=max_work
            )
            return VectorClip(result, inverse=True) if result is not None else None
        if first.inverse:
            a, b = b, a
        result = path_boolean(
            a, b, "difference", max_points=max_points, max_work=max_work
        )
        return VectorClip(result) if result is not None else False
    if isinstance(first, RectangleClip) and isinstance(second, RectangleClip):
        left, top = (
            max(round(first.left), round(second.left)),
            max(round(first.top), round(second.top)),
        )
        right, bottom = (
            min(round(first.right), round(second.right)),
            min(round(first.bottom), round(second.bottom)),
        )
        return (
            RectangleClip(left, top, right, bottom)
            if left < right and top < bottom
            else False
        )
    a, b = _path(first), _path(second)
    boundary = _convex(b, max_points)
    if boundary is None:
        boundary = _convex(a, max_points)
        if boundary is None:
            result = path_boolean(a, b, max_points=max_points, max_work=max_work)
            return VectorClip(result) if result is not None else False
        a = b
    result = intersect_convex(a, boundary, max_points=max_points)
    return VectorClip(result) if result is not None else False


class ClipResolver:
    """Cache pure mask callbacks by owner and absolute time, with bounded storage."""

    def __init__(
        self, evaluator: SceneEvaluator, max_points: int, max_work: int
    ) -> None:
        self.evaluator = evaluator
        self.max_points = max_points
        self.max_work = max_work
        self._cache: OrderedDict[tuple[str, float], ResolvedClip] = OrderedDict()

    def _resolve(
        self, node: SceneObject, time: float, state: VisualState
    ) -> ResolvedClip:
        clip = node.clip
        if clip is None:
            return None
        if isinstance(clip, RectangleClip):
            animated = clip.deform is not None
            if clip.deform is not None:
                bounds = clip.deform.sample(local_seconds(time, node.lifetime.start))
                if bounds is None:
                    return None if clip.inverse else False
                clip = replace(
                    clip,
                    left=bounds[0],
                    top=bounds[1],
                    right=bounds[2],
                    bottom=bounds[3],
                    deform=None,
                )
            if (
                animated
                and clip.space == "local"
                and state.transform.b == state.transform.c == 0
            ):
                a = state.transform.apply(Vec2(clip.left, clip.top))
                b = state.transform.apply(Vec2(clip.right, clip.bottom))
                if a.x == b.x or a.y == b.y:
                    return None if clip.inverse else False
                clip = RectangleClip(
                    min(a.x, b.x),
                    min(a.y, b.y),
                    max(a.x, b.x),
                    max(a.y, b.y),
                    inverse=clip.inverse,
                )
            if clip.space == "screen":
                if round(clip.left) >= round(clip.right) or round(clip.top) >= round(
                    clip.bottom
                ):
                    return None if clip.inverse else False
                return clip
            path = VectorPath.polygon(
                Vec2(clip.left, clip.top),
                Vec2(clip.right, clip.top),
                Vec2(clip.right, clip.bottom),
                Vec2(clip.left, clip.bottom),
            )
        else:
            path = clip.path
            if clip.deform is not None:
                try:
                    path = clip.deform.sample(
                        path, local_seconds(time, node.lifetime.start)
                    )
                except Exception as error:
                    raise ValueError(
                        f"clip callback: {type(error).__name__}: {error}"
                    ) from error
                if path is None:
                    return None if clip.inverse else False
                if path.point_count > clip.deform.max_points:
                    raise ValueError("clip callback exceeded its declared point bound")
        if path.point_count > self.max_points:
            raise ValueError("actual clip point budget exceeded")
        if clip.space == "local":
            if state.singular:
                return None if clip.inverse else False
            path = path.map(state.transform.apply)
        return VectorClip(path, inverse=clip.inverse)

    def combine(
        self,
        nodes: tuple[SceneObject, ...],
        time: float,
        leaf_state: VisualState,
    ) -> ResolvedMasks:
        result: ResolvedClip = None
        peak = 0
        for index, node in enumerate(nodes):
            if node.clip is None:
                continue
            try:
                key = (node.id, time)
                if key in self._cache:
                    clip = self._cache[key]
                    self._cache.move_to_end(key)
                else:
                    state = (
                        leaf_state
                        if index == len(nodes) - 1
                        else self.evaluator.at(node.id, time)
                    )
                    clip = self._resolve(node, time, state)
                    self._cache[key] = clip
                    if len(self._cache) > 128:
                        self._cache.popitem(last=False)
                peak = max(peak, _points(clip))
                if clip is False:
                    return ResolvedMasks(False, peak)
                if clip is None:
                    continue
                result = (
                    clip
                    if result is None
                    else _intersection(result, clip, self.max_points, self.max_work)
                )
                peak = max(peak, _points(result))
                if result is False:
                    return ResolvedMasks(False, peak)
            except (ValueError, TypeError) as error:
                raise SceneClipError(
                    str(error), object_id=node.id, origin=node.origin
                ) from error
        return ResolvedMasks(result, peak)
