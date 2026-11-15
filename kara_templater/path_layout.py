"""Place ordinary objects or annotated groups along a measured curve."""

from collections.abc import Iterable
from dataclasses import dataclass
from math import atan2, degrees

from .geometry import Contour, Vec2, finite
from .path_geometry import Polyline
from .scene import Lifetime, ObjectGroup, SceneObject
from .scene_animation import VisualState


@dataclass(frozen=True)
class PathItem:
    object: SceneObject
    advance: float
    anchor: Vec2 = Vec2()

    def __post_init__(self) -> None:
        finite(self.advance)
        if self.advance < 0:
            raise ValueError("path layout advances cannot be negative")


def layout_path(
    items: Iterable[PathItem],
    path: Contour | Polyline,
    *,
    id: str = "path-layout",
    start: float = 0,
    end: float = 1,
    orient: bool = True,
    position: Vec2 | None = None,
    max_items: int = 1000,
) -> ObjectGroup:
    """Distribute advance centers over a curve interval, using local anchor groups.

    Children retain their original coordinates, identity, lifetime, sources and
    local animations. An annotation grouped with its base follows the same tangent
    and parent transforms. The caller chooses spacing and the measured advance.
    """
    finite(start, end)
    if start == end or not 0 <= start <= 1 or not 0 <= end <= 1:
        raise ValueError("path layout needs distinct endpoints in 0..1")
    if type(max_items) is not int or max_items < 1:
        raise ValueError("path layout requires a positive object budget")
    prepared: list[PathItem] = []
    for item in items:
        if len(prepared) >= max_items:
            raise ValueError("path layout object budget exceeded")
        prepared.append(item)
    if not prepared or sum(item.advance for item in prepared) <= 0:
        raise ValueError("path layout requires objects with positive total advance")
    total = sum(item.advance for item in prepared)
    cursor = 0.0
    children: list[ObjectGroup] = []
    direction = 1 if end > start else -1
    for item in prepared:
        progress = start + (end - start) * (cursor + item.advance / 2) / total
        angle = 0.0
        if orient:
            delta = (
                path.point(min(1, progress + 1e-5))
                - path.point(max(0, progress - 1e-5))
            ) * direction
            if delta.length:
                angle = degrees(atan2(delta.y, delta.x))
        node = item.object
        local = node.copy(id=node.id, offset=item.anchor * -1)
        children.append(
            ObjectGroup(
                id=f"{id}/anchor:{node.id}",
                lifetime=node.lifetime,
                state=VisualState(position=path.point(progress), rotation=angle),
                children=(local,),
                origin=node.origin,
            )
        )
        cursor += item.advance
    lifetime = Lifetime(
        min(item.object.lifetime.start for item in prepared),
        max(item.object.lifetime.end for item in prepared),
    )
    return ObjectGroup(
        id=id,
        lifetime=lifetime,
        state=VisualState(position=Vec2() if position is None else position),
        children=tuple(children),
    )
