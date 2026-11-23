"""Reusable vector signals for karaoke tracks."""

from dataclasses import dataclass, replace
from math import cos, floor, log, pi, sin, sqrt
from typing import Literal

from ._karaoke_motion import zoom_pulse
from .composition import Color, Glow, Paint
from .cues import CueContent, CueContext, _SharedGradientCue
from .geometry import Contour, CubicSegment, LineSegment, Vec2, VectorPath, finite
from .lyric_highlights import LyricGradient
from .path_geometry import flatten, stroke
from .scene import Lifetime, ObjectGroup, PathObject, RectangleClip, RectangleKeyframes
from .scene_animation import (
    AnimationClip,
    FadeOut,
    StatePatch,
    Transform,
    Tween,
    VisualState,
)


def _rounded(width: float, height: float) -> VectorPath:
    radius = max(1, min(width, height) * 0.22)
    rx, ry = min(width / 2, radius), min(height / 2, radius)
    points: list[Vec2] = []
    corners = (
        (width - rx, ry),
        (width - rx, height - ry),
        (rx, height - ry),
        (rx, ry),
    )
    for i, (x, y) in enumerate(corners):
        for step in range(5):
            angle = (i - 1 + step / 4) * pi / 2
            points.append(Vec2(x + rx * cos(angle), y + ry * sin(angle)))
    return VectorPath.polygon(*points)


def _font_size(context: CueContext) -> float:
    return context.host.font_size if context.host is not None else 100.0


def _cue_size(explicit: float | None, ratio: float, context: CueContext) -> float:
    if explicit is not None:
        return explicit
    return max(4, floor(_font_size(context) * ratio + 0.5))


def _scaled_radius(radius: float, scale: float, width: float) -> float:
    # Studio rounds and caps each pen diameter before stacking the strokes.
    return min(floor(2 * radius * scale + 0.5), width // 2) / 2


def _cue_border(
    explicit: float | None,
    size: float,
    width: float,
    context: CueContext,
    paint: Paint | None = None,
) -> float:
    if explicit is not None:
        return explicit
    host = context.host
    if paint is not None and (context.role_font_size is not None or context.role_em is not None or host is not None):
        return _scaled_radius(paint.border, size / (context.role_font_size or _font_size(context)), width)
    if host is not None:
        return _scaled_radius(host.state.border, size / _font_size(context), width)
    return min(8, width // 2) / 2


def _gradient_shape(
    shape: PathObject, gradient: LyricGradient, width: float, height: float,
    start: float, end: float,
) -> PathObject:
    shadow = shape.state.shadow
    pad = shape.state.border + max(abs(shadow.x), abs(shadow.y)) + 4
    bounds = (-pad, -pad, width + pad, height + pad)
    return replace(
        shape, material=gradient._between(start, end),
        clip=RectangleClip(*bounds, space="local", deform=RectangleKeyframes(((0, bounds),))),
    )


def _decorated_shape(
    shape: PathObject, paint: Paint, size: float, width: float, context: CueContext
) -> tuple[PathObject, ...]:
    scale = size / (context.role_font_size or _font_size(context))
    layers = [shape]
    rim = paint.secondary_outline
    extra_radius = _scaled_radius(rim.width, scale, width) if rim else 0
    if rim and extra_radius:
        layers.insert(0, replace(shape, id=shape.id + "/secondary-outline", filled=False,
                                 material=None, clip=None,
                                 state=replace(shape.state, fill=rim.color, outline=rim.color,
                                               border=shape.state.border + extra_radius)))
    glow = paint.glow
    if glow and glow.opacity:
        halo = _cue_halo(shape, paint, glow, scale, width)
        if halo is not None:
            layers.insert(0, halo)
    # Only the outermost contour casts the cue shadow.
    return (layers[0], *(replace(layer, state=replace(layer.state, shadow=Vec2())) for layer in layers[1:]))


def _cue_halo(shape: PathObject, paint: Paint, glow: Glow, scale: float, width: float) -> PathObject | None:
    extra = max(0, glow.border - paint.border)
    extra_radius = _scaled_radius(extra, scale, width)
    blur = floor(glow.blur * scale + 0.5)
    if not extra_radius and not blur:
        return None
    path = shape.path
    border = shape.state.border + extra_radius
    if blur:
        # Studio blurs the pen silhouette. In libass a blurred ASS border also
        # includes the interior until the fill mask is subtracted at composition.
        pen_width = 2 * border + blur
        contours: list[Contour] = []
        for contour in path.contours:
            pen = stroke(flatten(contour), pen_width)
            if pen is not None:
                contours.extend(pen.contours)
        if not contours:
            return None
        path = VectorPath(tuple(contours))
        border = 0
    return replace(
        shape,
        id=shape.id + "/outer",
        path=path,
        material=None,
        clip=None,
        filled=bool(blur),
        state=replace(
            shape.state,
            fill=glow.color,
            outline=glow.color,
            border=border,
            # libass maps the ASS blur value to sigma by 2 / sqrt(log(256)).
            blur=blur * sqrt(log(256)) / 2,
            opacity=shape.state.opacity * glow.opacity,
        ),
    )


def _volume_flash(start: float, cycle: float, transition: float) -> tuple[AnimationClip, ...]:
    if transition == 0:
        # A hard flash goes dark for the middle half of each cycle.
        return (AnimationClip(start + cycle / 4, cycle / 2, Transform(opacity=0), hold=False),)
    # Studio's triangular pulse starts fading one sixth into the cycle.
    fade = cycle * transition / (6 * 0.67)
    return (
        AnimationClip(start + cycle / 6, fade, Tween(StatePatch(opacity=0))),
        AnimationClip(start + cycle * 5 / 6 - fade, fade, Tween(StatePatch(opacity=1))),
    )


@dataclass(frozen=True, kw_only=True)
class VolumeCue:
    """Descending inline columns. Flash together, then fill from left to right.

    The cue ends at its declared lifetime. count sets the column count; flashes
    sets the number of group pulses before the final fill. Each pulse and the
    fill get equal time by default; flash_ratio scales the length of each pulse
    relative to the fill. transition controls the softness of each flash from 0
    (hard blink) to 1. ratio is first-to-last column height and spacing is
    additional horizontal space in script pixels. Set countdown in seconds to leave the group visible
    and idle before the active portion. height and border use script pixels. Omit height to use size_ratio times the authored font size at the marker. column_width_ratio sets the width relative to height.
    align aligns the column tops, centers or bottoms.
    An omitted border scales the host outline, capped at a quarter of the column width.
    """

    count: int = 4
    height: float | None = None
    size_ratio: float = 0.5
    column_width_ratio: float = 0.25
    align: Literal["top", "center", "bottom"] = "center"
    border: float | None = None
    flashes: int = 3
    flash_ratio: float = 1
    transition: float = 0.67
    ratio: float = 3
    spacing: float = 0
    countdown: float | None = None
    sung: Color | None = None
    unsung: Color | None = None
    outline: Color | None = None

    def __post_init__(self) -> None:
        finite(self.flash_ratio, self.transition, self.ratio, self.spacing, self.size_ratio, self.column_width_ratio)
        if self.size_ratio <= 0 or self.column_width_ratio <= 0:
            raise ValueError("size_ratio and column_width_ratio must be positive")
        if self.align not in ("top", "center", "bottom"):
            raise ValueError("unknown volume column alignment")
        if not 0 <= self.transition <= 1:
            raise ValueError("transition must be between 0 and 1")
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
            clip
            for i in range(self.flashes if cycle else 0)
            for clip in _volume_flash(idle + cycle * i, cycle, self.transition)
        )
        size = _cue_size(self.height, self.size_ratio, context)
        width = max(1, floor(size * self.column_width_ratio + 0.5))
        host = context.host
        border = _cue_border(self.border, size, width, context)
        edge = 2 * border  # Studio reserves a full pen width on each side.
        pitch = width + 2 * edge + self.spacing
        group_right = edge + (self.count - 1) * pitch + width
        first = min(1.0, self.ratio) * size
        alignment = {"top": 0.0, "center": 0.5, "bottom": 1.0}[self.align]
        last = first / self.ratio
        bars = []
        shared_gradients: dict[str, LyricGradient] = {}
        for i in range(self.count):
            height = first + (last - first) * i / max(1, self.count - 1)
            change = max(life.start, life.end - fill * (1 - i / self.count))
            y = (size - height) * alignment
            height = max(1.0, height)
            path = _rounded(width, height)
            for start, end, color, paint in (
                (life.start, change, self.unsung, context.colors.before),
                (change, life.end, self.sung, context.colors.after),
            ):
                if end <= start:
                    continue
                animations: tuple[AnimationClip, ...] = ()
                if start == change and context.zoom_pulse_curve_level is not None:
                    note = fill / self.count
                    duration = min(end - start, note + 0.30)
                    motion = zoom_pulse(
                        note,
                        duration,
                        context.zoom_pulse_curve_level,
                        Vec2(width / 2, height / 2),
                    )
                    animations = (AnimationClip(0, duration, motion),)
                shape = PathObject(
                    animations=animations,
                    id=f"{context.id}/column:{i}:{start}",
                    lifetime=Lifetime(start, end),
                    path=path,
                    state=VisualState(
                        position=Vec2(edge + i * pitch, y),
                        fill=color or paint.fill,
                        outline=self.outline or paint.outline,
                        opacity=paint.opacity,
                        border=_cue_border(self.border, size, width, context, paint),
                        shadow=(
                            host.state.shadow * (size / _font_size(context))
                            if host
                            else Vec2(3, 3)
                        ),
                    ),
                    origin=context.origin,
                )
                gradient = context.gradient if start == change else context.base_gradient
                if gradient is not None and color is None:
                    x, y = shape.state.position.x, shape.state.position.y
                    limits = (edge - x, group_right - x) if gradient.axis == "x" else (-y, size - y)
                    shape = _gradient_shape(shape, gradient, width, height, *limits)
                    if gradient.axis == "x":
                        shared_gradients[shape.id] = gradient
                bars.extend(_decorated_shape(shape, paint, size, width, context))
        group = ObjectGroup(
            id=f"{context.id}/volume",
            lifetime=life,
            animations=flashes,
            children=tuple(bars),
            origin=context.origin,
        )
        content = CueContent((group,), self.count * pitch - self.spacing, size)
        if not shared_gradients:
            return content

        def share(left: float, right: float) -> tuple[ObjectGroup, ...]:
            # The binder now knows all inline reservations and the lyric's right edge.
            children = []
            for bar in bars:
                gradient = shared_gradients.get(bar.id)
                if gradient is not None:
                    x = bar.state.position.x
                    bar = replace(bar, material=gradient._between(left - x, right - x))
                children.append(bar)
            return (replace(group, children=tuple(children)),)

        return _SharedGradientCue(content.objects, content.width, size, edge, share)


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

    size is the side of a lamp in script pixels, defaulting to size_ratio times the authored font size at the marker. Each lamp fades over the last
    transition fraction of its step. Pass a custom path in the unit square to
    use a drawn symbol with the same layout and clock. spacing adds script pixels between lamps.
    Set countdown in seconds to keep all lamps lit before the active steps.
    """

    shape: (
        Literal["circle", "square", "rounded", "star", "note8", "note16", "notepair"]
        | VectorPath
    ) = "circle"
    direction: Literal["left_to_right", "right_to_left"] = "right_to_left"
    size: float | None = None
    size_ratio: float = 0.5
    spacing: float = 0
    countdown: float | None = None
    transition: float = 0.67
    slide: Vec2 = Vec2()
    color: Color | None = None
    outline: Color | None = None
    border: float | None = None
    edge_brightness: float = 0.6

    def __post_init__(self) -> None:
        if self.direction not in ("left_to_right", "right_to_left"):
            raise ValueError("unknown signal direction")
        if self.size is not None:
            finite(self.size)
        if self.border is not None:
            finite(self.border)
        finite(self.transition, self.edge_brightness, self.spacing, self.size_ratio)
        if self.size_ratio <= 0:
            raise ValueError("size_ratio must be positive")
        if self.spacing < 0:
            raise ValueError("spacing must be nonnegative")
        if self.countdown is not None:
            finite(self.countdown)
            if self.countdown <= 0:
                raise ValueError("countdown must be positive")
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
        size = _cue_size(self.size, self.size_ratio, context)
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
            path = _rounded(size, size)
        else:
            path = VectorPath.polygon(
                *(
                    Vec2(size / 2, size / 2)
                    + Vec2(sin(i * pi / 5), -cos(i * pi / 5))
                    * (size * (0.225 if i % 2 else 0.5))
                    for i in range(10)
                )
            )
        border = _cue_border(self.border, size, size, context, context.colors.after)
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
        shadow = host.state.shadow * (size / _font_size(context)) if host else Vec2()
        nodes = []
        steps = context.steps
        cue_end = context.lifetime.end
        duration = cue_end - context.lifetime.start
        if self.countdown is not None and self.countdown < duration:
            steps = tuple(cue_end - (cue_end - t) * self.countdown / duration for t in steps)
        count = len(steps) - 1
        pitch = size * 1.5 + self.spacing
        group_width = size + (count - 1) * pitch
        for i, (start, end) in enumerate(
            zip(steps[:-1], steps[1:], strict=True)
        ):
            fade = (end - start) * self.transition
            slot = i if self.direction == "left_to_right" else count - 1 - i
            origin = Vec2(slot * pitch, 0)
            exit_motion = (
                Tween(StatePatch(position=origin + self.slide, opacity=0))
                if self.slide != Vec2()
                else FadeOut()
            )
            lamp_id = f"{context.id}/lamp:{i}"
            life = Lifetime(context.lifetime.start, end)
            shape = PathObject(
                id=f"{lamp_id}/shape",
                lifetime=life,
                path=path,
                origin=context.origin,
                state=VisualState(
                    fill=self.color or context.colors.after.fill,
                    outline=self.outline or context.colors.after.outline,
                    border=border,
                    shadow=shadow,
                ),
            )
            gradient = context.gradient
            if gradient is not None and self.color is None:
                # All slots keep their original colors as the countdown shrinks.
                left, right = (0.0, size)
                if gradient.axis == "x":
                    left, right = -origin.x, group_width - origin.x
                shape = _gradient_shape(shape, gradient, size, size, left, right)
            children = list(
                _decorated_shape(shape, context.colors.after, size, size, context)
            )
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
            if context.zoom_pulse_curve_level is not None:
                duration = end - start
                motion = zoom_pulse(
                    duration,
                    duration,
                    context.zoom_pulse_curve_level,
                    Vec2(size / 2, size / 2),
                )
                children = [
                    child.animate(motion, at=start - life.start, duration=duration)
                    for child in children
                ]
            nodes.append(
                ObjectGroup(
                    id=lamp_id,
                    lifetime=life,
                    children=tuple(children),
                    origin=context.origin,
                    state=VisualState(
                        position=origin, opacity=context.colors.after.opacity
                    ),
                    animations=(
                        AnimationClip(
                            end - context.lifetime.start - fade, fade, exit_motion
                        ),
                    )
                    if fade
                    else (),
                )
            )
        return CueContent(tuple(nodes), group_width, size)
