"""Reusable vector signals for karaoke tracks."""

from dataclasses import dataclass
from math import cos, floor, pi, sin
from typing import Literal

from .composition import Color
from .cues import CueContent, CueContext
from .geometry import Contour, CubicSegment, LineSegment, Vec2, VectorPath, finite
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


def _cue_size(explicit: float | None, context: CueContext) -> float:
    if explicit is not None:
        return explicit
    host = context.host
    font_size = host.font_size * host.state.scale.y if host else 100
    return max(4, floor(font_size / 2 + 0.5))


def _cue_border(
    explicit: float | None, size: float, width: float, context: CueContext
) -> float:
    if explicit is not None:
        return explicit
    host = context.host
    pen = floor(2 * host.state.border * size / host.font_size + 0.5) if host else 8
    return min(pen, width // 2) / 2


@dataclass(frozen=True, kw_only=True)
class VolumeCue:
    """Descending inline columns. Flash together, then fill from left to right.

    The cue ends at its declared lifetime. count sets the column count; flashes
    sets the number of group pulses before the final fill. Each pulse and the
    fill get equal time by default; flash_ratio scales the length of each pulse
    relative to the fill. ratio is first-to-last column height and spacing is
    additional horizontal space in script pixels. Set countdown in seconds to leave the group visible
    and idle before the active portion. height and border use script pixels. Omit height for half the host font size.
    An omitted border scales the host outline, capped at a quarter of the column width.
    """

    count: int = 4
    height: float | None = None
    border: float | None = None
    flashes: int = 3
    flash_ratio: float = 1
    ratio: float = 3
    spacing: float = 0
    countdown: float | None = None
    sung: Color = Color(255, 90, 111)
    unsung: Color = Color(255, 255, 255)
    outline: Color = Color(34, 34, 34)

    def __post_init__(self) -> None:
        finite(self.flash_ratio, self.ratio, self.spacing)
        for dimension in (self.height, self.border):
            if dimension is not None:
                finite(dimension)
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
        if (self.height is not None and self.height <= 0) or (
            self.border is not None and self.border < 0
        ):
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
        size = _cue_size(self.height, context)
        width = max(1, floor(size / 4 + 0.5))
        host = context.host
        border = _cue_border(self.border, size, width, context)
        edge = 2 * border  # Studio reserves a full pen width on each side.
        pitch = width + 2 * edge + self.spacing
        first = min(1.0, self.ratio) * size
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
                            position=Vec2(edge + i * pitch, (size - height) / 2),
                            fill=color,
                            outline=self.outline,
                            border=border,
                            shadow=(
                                host.state.shadow * (size / host.font_size)
                                if host
                                else Vec2(3, 3)
                            ),
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
        return CueContent((group,), self.count * pitch - self.spacing, size)


def _note(shape: str, size: float) -> VectorPath:
    from .path_boolean import path_boolean

    def stem(x: float, y: float, w: float, h: float) -> VectorPath:
        return VectorPath.rectangle(w, h).map(lambda p: p + Vec2(x, y))

    def head(x: float, y: float, w: float, h: float) -> VectorPath:
        return VectorPath.circle(1).map(lambda p: Vec2(x + w * p.x, y + h * p.y))

    if shape == "notepair":
        parts = [
            head(0.24, 0.74, 0.17, 0.11),
            stem(0.342, 0.16, 0.06, 0.60),
            head(0.62, 0.60, 0.17, 0.11),
            stem(0.722, 0.04, 0.06, 0.58),
            VectorPath.polygon(
                Vec2(0.342, 0.08),
                Vec2(0.782, 0.02),
                Vec2(0.782, 0.12),
                Vec2(0.342, 0.18),
            ),
        ]
    else:
        parts = [head(0.34, 0.78, 0.20, 0.12), stem(0.468, 0.10, 0.064, 0.70)]
        flag = VectorPath(
            (
                Contour(
                    Vec2(0.532, 0),
                    (
                        CubicSegment(
                            Vec2(0.747, 0.06), Vec2(0.827, 0.20), Vec2(0.707, 0.36)
                        ),
                        LineSegment(Vec2(0.632, 0.285)),
                        CubicSegment(
                            Vec2(0.722, 0.18), Vec2(0.647, 0.09), Vec2(0.532, 0.055)
                        ),
                    ),
                ),
            )
        )
        for y in (0.10, 0.26) if shape == "note16" else (0.10,):
            parts.append(flag.map(lambda p, dy=y: p + Vec2(0, dy)))
    path = parts[0]
    for part in parts[1:]:
        merged = path_boolean(path, part, "union", tolerance=0.002)
        assert merged is not None
        path = merged
    return path.map(lambda p: p * size)


@dataclass(frozen=True, kw_only=True)
class SignalCue:
    """A row of vector lamps extinguishing on cue steps, right to left by default.

    size is the side of a lamp in script pixels, defaulting to half the host font size. Each lamp fades over the last
    transition fraction of its step. Pass a custom path in the unit square to
    use a drawn symbol with the same layout and clock.
    """

    shape: (
        Literal["circle", "square", "rounded", "star", "note8", "note16", "notepair"]
        | VectorPath
    ) = "circle"
    direction: Literal["left_to_right", "right_to_left"] = "right_to_left"
    size: float | None = None
    transition: float = 0.67
    slide: Vec2 = Vec2()
    color: Color = Color(255, 90, 111)
    outline: Color = Color(34, 34, 34)
    border: float | None = None
    edge_brightness: float = 0.6

    def __post_init__(self) -> None:
        if self.direction not in ("left_to_right", "right_to_left"):
            raise ValueError("unknown signal direction")
        if self.size is not None:
            finite(self.size)
        if self.border is not None:
            finite(self.border)
        finite(self.transition, self.edge_brightness)
        if (
            (self.size is not None and self.size <= 0)
            or not 0 <= self.transition <= 1
            or (self.border is not None and self.border < 0)
            or not 0 <= self.edge_brightness <= 1
        ):
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
        size = _cue_size(self.size, context)
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
        border = _cue_border(self.border, size, size, context)
        highlight = None
        if self.edge_brightness and isinstance(self.shape, str):
            x, y, radius = {
                "star": (0.5, 0.36, 0.10),
                "note8": (0.29, 0.745, 0.06),
                "note16": (0.29, 0.745, 0.06),
                "notepair": (0.20, 0.705, 0.055),
            }.get(self.shape, (0.34, 0.34, 0.16))
            highlight = VectorPath.circle(radius * size).map(
                lambda p: p + Vec2(x, y) * size
            )
        host = context.host
        shadow = host.state.shadow * (size / host.font_size) if host else Vec2()
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
            lamp_id = f"{context.id}/lamp:{i}"
            life = Lifetime(context.lifetime.start, end)
            children = [
                PathObject(
                    id=f"{lamp_id}/shape",
                    lifetime=life,
                    path=path,
                    origin=context.origin,
                    state=VisualState(
                        fill=self.color,
                        outline=self.outline,
                        border=border,
                        shadow=shadow,
                    ),
                )
            ]
            if highlight is not None:
                children.append(
                    PathObject(
                        id=f"{lamp_id}/highlight",
                        lifetime=life,
                        path=highlight,
                        origin=context.origin,
                        state=VisualState(opacity=0.55 * self.edge_brightness),
                        layer=1,
                    )
                )
            nodes.append(
                ObjectGroup(
                    id=lamp_id,
                    lifetime=life,
                    children=tuple(children),
                    origin=context.origin,
                    state=VisualState(position=origin),
                    animations=(
                        AnimationClip(
                            end - context.lifetime.start - fade, fade, exit_motion
                        ),
                    )
                    if fade
                    else (),
                )
            )
        return CueContent(tuple(nodes), size * (1 + (count - 1) * 1.5), size)
