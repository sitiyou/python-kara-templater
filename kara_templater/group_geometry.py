"""Source-preserving geometric unions for shared outlines and whole-word glow."""

from dataclasses import replace
from functools import lru_cache

from .ass import Document
from .geometry import Vec2, VectorPath, finite
from .path_animation import PathFunction
from .path_boolean import path_boolean
from .path_geometry import GeometryError
from .scene import ObjectGroup, PathObject, Scene, SceneObject, TextObject
from .scene_animation import VisualState
from .sources import EventOrigin
from .text_geometry import outline_text


def merge_geometry(
    group: ObjectGroup,
    *,
    id: str | None = None,
    tolerance: float = 0.25,
    max_points: int = 4096,
    max_work: int = 1_000_000,
) -> PathObject:
    """Union child geometry, then paint one ordinary PathObject.

    Child colors, opacity, border, blur and layer order do not participate in
    this geometric operation. Root transforms, animations, opacity, clip and
    reference are retained. Descendant clips/references require explicit prior
    lowering and are rejected. This is not an offscreen alpha-composite group.
    """
    finite(tolerance)
    if (
        tolerance <= 0
        or type(max_points) is not int
        or max_points < 3
        or type(max_work) is not int
        or max_work < 1
    ):
        raise ValueError(
            "geometry union needs positive tolerance/work and max_points >= 3"
        )
    local = replace(
        group, state=VisualState(), animations=(), clip=None, reference=None
    )
    leaves: list[tuple[TextObject | PathObject, float, float]] = []
    outlines: dict[str, VectorPath | None] = {}
    origins: list[EventOrigin] = []
    points: set[float] = set()
    dynamic = False

    def visit(node: SceneObject, start: float, end: float) -> None:
        nonlocal dynamic
        if node.clip is not None or node.reference is not None:
            raise GeometryError(
                f"{node.id}: merge_geometry requires unclipped descendants without world references"
            )
        start, end = max(start, node.lifetime.start), min(end, node.lifetime.end)
        if end <= start:
            return
        if node.origin is not None:
            origins.append(node.origin)
        points.update((start, end))
        dynamic |= start != group.lifetime.start or end != group.lifetime.end
        for clip in node.animations:
            if clip.animation.channels & frozenset(
                ("position", "scale", "rotation", "skew")
            ):
                dynamic = True
                points.update(
                    node.time_origin + value
                    for value in (
                        clip.start,
                        clip.end,
                        *(clip.start + value for value in clip.breakpoints),
                    )
                )
        if isinstance(node, ObjectGroup):
            for child in node.children:
                visit(child, start, end)
            return
        if isinstance(node, TextObject):
            if "\n" in node.text:
                raise GeometryError(
                    f"{node.id}: merged text outlines require single-line text"
                )
            outlines[node.id] = outline_text(node, max_points=max_points).path
        else:
            if node.path.point_count > max_points or (
                node.deform is not None and node.deform.max_points > max_points
            ):
                raise GeometryError(
                    f"{node.id}: declared merged geometry point budget exceeded"
                )
            if node.deform is not None:
                dynamic = True
                points.update(
                    node.time_origin + value for value in node.deform.breakpoints
                )
        leaves.append((node, start, end))

    for child in local.children:
        visit(child, group.lifetime.start, group.lifetime.end)

    evaluator = Scene(Document.create()).add(local).evaluator()

    @lru_cache(maxsize=128)
    def union(paths: tuple[VectorPath, ...]) -> VectorPath | None:
        result: VectorPath | None = None
        for path in paths:
            result = path_boolean(
                path if result is None else result,
                path,
                "union",
                tolerance=tolerance,
                max_points=2 * max_points,
                max_work=max_work,
            )
            if result is not None and result.point_count > max_points:
                raise GeometryError("merged geometry result point budget exceeded")
        return result

    def sample(base: VectorPath, time: float) -> VectorPath | None:
        absolute = group.lifetime.start + time
        paths: list[VectorPath] = []
        for node, start, end in leaves:
            if not start <= absolute < end:
                continue
            state = evaluator.at(node.id, absolute)
            if state.singular:
                continue
            path = (
                outlines[node.id]
                if isinstance(node, TextObject)
                else node.path_at(absolute)
            )
            if path is not None:
                paths.append(path.map(state.transform.apply))
        return union(tuple(paths))

    placeholder = VectorPath.polygon(Vec2(), Vec2(), Vec2())
    # Static geometry is built now; dynamic callbacks are left to the compiler,
    # whose declared point/event preflight must precede user callback execution.
    initial = None if dynamic else sample(placeholder, 0)
    origin = group.origin
    if origin is None and origins:
        origin = EventOrigin(
            tuple(dict.fromkeys(source for item in origins for source in item.sources)),
            "merged geometry",
            tuple(dict.fromkeys(track for item in origins for track in item.track_ids)),
        )
    return PathObject(
        id=f"{group.id}/geometry" if id is None else id,
        lifetime=group.lifetime,
        path=placeholder if initial is None else initial,
        deform=PathFunction(
            sample,
            max_points=max_points,
            breakpoints=tuple(
                sorted(
                    value - group.lifetime.start
                    for value in points
                    if group.lifetime.start <= value <= group.lifetime.end
                )
            ),
        )
        if dynamic or initial is None
        else None,
        state=group.state,
        animations=group.animations,
        layer=group.layer,
        clip=group.clip,
        reference=group.reference,
        origin=origin,
    )
