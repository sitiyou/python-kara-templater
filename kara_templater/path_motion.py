"""Typed motion along parameterized or arc-length sampled paths."""

from collections.abc import Callable
from dataclasses import dataclass, replace
from math import atan2, degrees

from .geometry import Contour, LineSegment, Vec2, finite
from .path_geometry import Polyline
from .scene_animation import Channel, VisualState, linear_rate


@dataclass(frozen=True)
class MoveAlong:
    """Offset the captured position by a path; optionally follow its tangent.

    Contour uses its curve parameter. Polyline uses its approximate arc length.
    The rate function chooses progress, which is clamped to the path endpoints.
    """

    path: Contour | Polyline
    rate: Callable[[float], float] = linear_rate
    orient: bool = False

    @property
    def channels(self) -> frozenset[Channel]:
        """The position and optional rotation channels written by this motion."""
        return (
            frozenset(("position", "rotation"))
            if self.orient
            else frozenset(("position",))
        )

    @property
    def native_linear(self) -> bool:
        """Whether the declared path and rate support the compiler native linear-motion strategy."""
        if self.orient or self.rate is not linear_rate or self.path.point(0) != Vec2():
            return False
        if isinstance(self.path, Polyline):
            return len(self.path.points) == 2
        return (
            not self.path.closed
            and len(self.path.segments) == 1
            and isinstance(self.path.segments[0], LineSegment)
        )

    def sample(self, base: VisualState, progress: float) -> VisualState:
        """Evaluate path position and optional tangent orientation at normalized progress."""
        value = self.rate(progress)
        finite(value)
        value = max(0, min(1, value))
        rotation = base.rotation
        if self.orient:
            direction = self.path.point(min(1, value + 1e-5)) - self.path.point(
                max(0, value - 1e-5)
            )
            if direction.length:
                rotation += degrees(atan2(direction.y, direction.x))
        return replace(
            base, position=base.position + self.path.point(value), rotation=rotation
        )
