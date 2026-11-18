"""Reusable vector signals for karaoke tracks."""

from dataclasses import dataclass
from math import cos, pi, sin
from typing import Literal

from .composition import Color
from .cues import CueContent, CueContext
from .geometry import Vec2, VectorPath, finite
from .scene import Lifetime, ObjectGroup, PathObject
from .scene_animation import AnimationClip, FadeOut, StatePatch, Tween, VisualState


def _rounded(width: float, height: float, radius: float) -> VectorPath:
    points: list[Vec2] = []
    corners = (
        (width - radius, radius),
        (width - radius, height - radius),
        (radius, height - radius),
        (radius, radius),
    )
    for i, (x, y) in enumerate(corners):
        for step in range(5):
            angle = (i - 1 + step / 4) * pi / 2
            points.append(Vec2(x + radius * cos(angle), y + radius * sin(angle)))
    return VectorPath.polygon(*points)


@dataclass(frozen=True, kw_only=True)
class VolumeCue:
    """Descending inline columns. Flash together, then fill from left to right.

    The cue ends at its declared lifetime. count sets the column count; flashes
    sets the number of group pulses before the final fill. Each pulse and the
    fill get equal time by default; flash_ratio scales the length of each pulse
    relative to the fill. ratio is first-to-last column height and spacing is
    additional horizontal space in script pixels. Set countdown in seconds to leave the group visible
    and idle before the active portion. height and border use script pixels.
    """

    count: int = 4
    height: float = 50
    border: float = 4
    flashes: int = 3
    flash_ratio: float = 1
    ratio: float = 3
    spacing: float = 0
    countdown: float | None = None
    sung: Color = Color(255, 90, 111)
    unsung: Color = Color(255, 255, 255)
    outline: Color = Color(34, 34, 34)

    def __post_init__(self) -> None:
        finite(self.height, self.border, self.flash_ratio, self.ratio, self.spacing)
        if (
            type(self.count) is not int
            or self.count < 1
            or type(self.flashes) is not int
            or self.flashes < 0
        ):
            raise ValueError("count must be positive and flashes nonnegative integers")
        if self.flash_ratio < 0 or self.ratio <= 0 or self.spacing < 0:
            raise ValueError(
                "flash_ratio and spacing must be nonnegative and ratio positive"
            )
        if self.height <= 0 or self.border < 0:
            raise ValueError("height must be positive and border nonnegative")
        if self.countdown is not None:
            finite(self.countdown)
            if self.countdown <= 0:
                raise ValueError("countdown must be positive")

    def __call__(self, context: CueContext) -> CueContent:
        """Build seekable pulses and column fills ending at the cue boundary."""
        life = context.lifetime
        duration = life.end - life.start
        active = min(self.countdown or duration, duration)
        fill = active / (self.flashes * self.flash_ratio + 1)
        cycle = fill * self.flash_ratio
        idle = duration - active
        flashes = tuple(
            AnimationClip(
                idle + cycle * (i + phase),
                cycle / 6,
                Tween(StatePatch(opacity=opacity)),
            )
            for i in range(self.flashes if cycle else 0)
            for phase, opacity in ((1 / 6, 0), (2 / 3, 1))
        )
        width = max(1, round(self.height / 4))
        edge = self.border + 1
        pitch = width + 2 * edge + self.spacing
        first = min(1.0, self.ratio) * self.height
        last = first / self.ratio
        bars = []
        for i in range(self.count):
            height = first + (last - first) * i / max(1, self.count - 1)
            change = max(life.start, life.end - fill * (1 - i / self.count))
            path = _rounded(width, height, min(width, height) * 0.22)
            for start, end, color in (
                (life.start, change, self.unsung),
                (change, life.end, self.sung),
            ):
                if end <= start:
                    continue
                bars.append(
                    PathObject(
                        id=f"{context.id}/column:{i}:{start}",
                        lifetime=Lifetime(start, end),
                        path=path,
                        state=VisualState(
                            position=Vec2(edge + i * pitch, (self.height - height) / 2),
                            fill=color,
                            outline=self.outline,
                            border=self.border,
                            shadow=Vec2(3, 3),
                        ),
                        origin=context.origin,
                    )
                )
        group = ObjectGroup(
            id=f"{context.id}/volume",
            lifetime=life,
            animations=flashes,
            children=tuple(bars),
            origin=context.origin,
        )
        return CueContent((group,), self.count * pitch - self.spacing, self.height)


def _note(shape: str, size: float) -> VectorPath:
    from .path_boolean import path_boolean

    def stem(x: float, top: float, bottom: float) -> VectorPath:
        return VectorPath.rectangle(0.08, bottom - top).map(lambda p: p + Vec2(x, top))

    def head(x: float, y: float) -> VectorPath:
        return VectorPath.circle(1).map(lambda p: Vec2(x + 0.18 * p.x, y + 0.12 * p.y))

    if shape == "notepair":
        parts = [
            head(0.23, 0.8),
            stem(0.32, 0.19, 0.82),
            head(0.73, 0.7),
            stem(0.82, 0.09, 0.72),
            VectorPath.polygon(
                Vec2(0.32, 0.14), Vec2(0.9, 0.04), Vec2(0.9, 0.18), Vec2(0.32, 0.28)
            ),
        ]
    else:
        parts = [head(0.35, 0.8), stem(0.44, 0.08, 0.82)]
        for y in (0.08, 0.29) if shape == "note16" else (0.08,):
            parts.append(
                VectorPath.polygon(
                    Vec2(0.49, y),
                    Vec2(0.78, y + 0.18),
                    Vec2(0.72, y + 0.35),
                    Vec2(0.66, y + 0.22),
                    Vec2(0.49, y + 0.11),
                )
            )
    path = parts[0]
    for part in parts[1:]:
        merged = path_boolean(path, part, "union", tolerance=0.002)
        assert merged is not None
        path = merged
    return path.map(lambda p: p * size)


@dataclass(frozen=True, kw_only=True)
class SignalCue:
    """A row of vector lamps extinguishing on cue steps, right to left by default.

    size is the side of a lamp in script pixels. Each lamp fades over the last
    transition fraction of its step. Pass a custom path in the unit square to
    use a drawn symbol with the same layout and clock.
    """

    shape: (
        Literal["circle", "square", "rounded", "star", "note8", "note16", "notepair"]
        | VectorPath
    ) = "circle"
    direction: Literal["left_to_right", "right_to_left"] = "right_to_left"
    size: float = 50
    transition: float = 0.67
    slide: Vec2 = Vec2()
    color: Color = Color(255, 90, 111)
    outline: Color = Color(34, 34, 34)
    border: float = 2

    def __post_init__(self) -> None:
        if self.direction not in ("left_to_right", "right_to_left"):
            raise ValueError("unknown signal direction")
        finite(self.size, self.transition, self.border)
        if self.size <= 0 or not 0 <= self.transition <= 1 or self.border < 0:
            raise ValueError("invalid signal size, transition or border")
        if not isinstance(self.shape, VectorPath) and self.shape not in (
            "circle",
            "square",
            "rounded",
            "star",
            "note8",
            "note16",
            "notepair",
        ):
            raise ValueError("unknown lamp shape")

    def __call__(self, context: CueContext) -> CueContent:
        """Place lamp shapes on their own intervals within the cue lifetime."""
        size = self.size
        if isinstance(self.shape, VectorPath):
            path = self.shape.map(lambda p: p * size)
        elif self.shape in ("note8", "note16", "notepair"):
            path = _note(self.shape, size)
        elif self.shape == "circle":
            path = VectorPath.circle(size / 2).map(
                lambda p: p + Vec2(size / 2, size / 2)
            )
        elif self.shape == "square":
            path = VectorPath.rectangle(size, size)
        elif self.shape == "rounded":
            path = _rounded(size, size, size * 0.22)
        else:
            path = VectorPath.polygon(
                *(
                    Vec2(size / 2, size / 2)
                    + Vec2(sin(i * pi / 5), -cos(i * pi / 5))
                    * (size * (0.225 if i % 2 else 0.5))
                    for i in range(10)
                )
            )
        nodes = []
        count = len(context.steps) - 1
        for i, (start, end) in enumerate(
            zip(context.steps[:-1], context.steps[1:], strict=True)
        ):
            fade = (end - start) * self.transition
            slot = i if self.direction == "left_to_right" else count - 1 - i
            origin = Vec2(slot * size * 1.5, 0)
            exit_motion = (
                Tween(StatePatch(position=origin + self.slide, opacity=0))
                if self.slide != Vec2()
                else FadeOut()
            )
            nodes.append(
                PathObject(
                    id=f"{context.id}/lamp:{i}",
                    lifetime=Lifetime(context.lifetime.start, end),
                    path=path,
                    state=VisualState(
                        position=origin,
                        fill=self.color,
                        outline=self.outline,
                        border=self.border,
                    ),
                    animations=(
                        AnimationClip(
                            end - context.lifetime.start - fade, fade, exit_motion
                        ),
                    )
                    if fade
                    else (),
                    origin=context.origin,
                )
            )
        return CueContent(tuple(nodes), size * (1 + (count - 1) * 1.5), size)
