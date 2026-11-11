"""Compile explicit karaoke text layers to ASS without executable templates."""

from collections.abc import Iterable
from dataclasses import dataclass, field
from itertools import pairwise
from math import floor
from typing import Literal

from .animation import OffsetAnimation, OpacityAnimation, ScaleAnimation
from .ass import Line, Style
from .composition import Color, Paint
from .model import Box
from .sources import EventOrigin
from .timeline import (
    DisplayWindow,
    EdgeSweep,
    Region,
    SingingPass,
    _finite,
    _milliseconds,
)


class OutputCapabilityError(ValueError):
    """An output failure with optional source and absolute-time context."""

    def __init__(
        self,
        message: str,
        *,
        origin: EventOrigin | None = None,
        time_ms: float | None = None,
    ) -> None:
        super().__init__(message)
        self.origin = origin
        self.time_ms = time_ms
        if origin is not None:
            self.add_note(
                f"effect={origin.effect}; sources={origin.sources!r}; "
                f"tracks={origin.track_ids!r}"
            )


def number(value: float) -> str:
    _finite(value, "ASS number")
    # Center anchors can lie on half of the 1/64 px glyph grid. Six decimal
    # places can round across libass's next grid boundary during placement.
    return format(value, ".9f").rstrip("0").rstrip(".") if value else "0"


def color(value: Color) -> str:
    return f"&H{value.blue:02X}{value.green:02X}{value.red:02X}&"


def alpha(opacity: float) -> str:
    _finite(opacity, "opacity")
    if not 0 <= opacity <= 1:
        raise ValueError("opacity must be in 0..1")
    return f"&H{floor(255 * (1 - opacity) + 0.5):02X}&"


def escape_text(text: str) -> str:
    # A word joiner makes a literal backslash unable to start an ASS escape.
    if "\r" in text or "\x00" in text:
        raise ValueError("ASS text cannot contain CR or NUL")
    return (
        text.replace("\\", "\\\u2060")
        .replace("{", "\\{")
        .replace("}", "\\}")
        .replace("\n", r"\N")
    )


def quantize(time_ms: float) -> int:
    """Nearest centisecond, with half steps rounded forward, shared by all layers."""
    _finite(time_ms, "time")
    return floor(time_ms / 10 + 0.5) * 10


@dataclass(frozen=True)
class Fade:
    in_ms: int = 0
    out_ms: int = 0

    def __post_init__(self) -> None:
        _milliseconds(self.in_ms, "fade in")
        _milliseconds(self.out_ms, "fade out")

    def opacity_at(self, time_ms: float, window: DisplayWindow) -> float:
        if self.in_ms + self.out_ms > window.end_ms - window.start_ms:
            raise ValueError("fade durations exceed the display window")
        before = (
            min(1, max(0, (time_ms - window.start_ms) / self.in_ms))
            if self.in_ms
            else 1
        )
        after = (
            min(1, max(0, (window.end_ms - time_ms) / self.out_ms))
            if self.out_ms
            else 1
        )
        return min(before, after)


@dataclass(frozen=True)
class ClipSpan:
    """A linear rectangular mask over a half-open absolute time interval.

    Separate spans allow instantaneous resets without ambiguous duplicate keys.
    Coordinates are in the original text layout and follow scale transforms.
    """

    start_ms: float
    end_ms: float
    start: Region
    end: Region

    def __post_init__(self) -> None:
        _finite(self.start_ms, "clip start")
        _finite(self.end_ms, "clip end")
        if self.end_ms <= self.start_ms:
            raise ValueError("clip spans require positive duration")

    def at(self, time_ms: float) -> Region:
        t = min(1, max(0, (time_ms - self.start_ms) / (self.end_ms - self.start_ms)))
        return Region(
            self.start.left + (self.end.left - self.start.left) * t,
            self.start.right + (self.end.right - self.start.right) * t,
        )


DEFAULT_EDGES = EdgeSweep()


def sweep_spans(
    singing: SingingPass,
    *,
    paint: Region,
    window: DisplayWindow,
    edges: EdgeSweep = DEFAULT_EDGES,
) -> tuple[ClipSpan, ...]:
    """One traversal including decoration transitions and post-singing hold."""
    if paint.left > singing.region.left or paint.right < singing.region.right:
        raise ValueError("paint region must enclose timing region")
    left, right = paint.left - edges.padding_px, paint.right + edges.padding_px
    body = singing.region
    segments: list[ClipSpan] = []

    def add(start, end, x0, x1):
        if end > start:
            segments.append(ClipSpan(start, end, Region(left, x0), Region(left, x1)))

    add(singing.start_ms - edges.lead_ms, singing.start_ms, left, body.left)
    for (t0, p0), (t1, p1) in pairwise(singing.curve.knots):
        duration = singing.end_ms - singing.start_ms
        add(
            singing.start_ms + duration * t0,
            singing.start_ms + duration * t1,
            body.at(p0),
            body.at(p1),
        )
    add(singing.end_ms, singing.end_ms + edges.tail_ms, body.right, right)
    add(singing.end_ms + edges.tail_ms, window.end_ms, right, right)
    return tuple(
        s for s in segments if s.end_ms > window.start_ms and s.start_ms < window.end_ms
    )


@dataclass(frozen=True)
class TextLayer:
    source_id: str
    text: str
    style: Style
    box: Box
    window: DisplayWindow
    paint: Paint = field(default_factory=Paint)
    fade: Fade = Fade()
    clips: tuple[ClipSpan, ...] | None = None
    animations: tuple[ScaleAnimation, ...] = ()
    order: int = 0
    animation_id: str | None = None
    active_window: DisplayWindow | None = None
    origin: EventOrigin | None = None
    component: Literal["both", "fill", "glow"] = "both"
    fade_window: DisplayWindow | None = None
    opacity_animations: tuple[OpacityAnimation, ...] = ()
    offsets: tuple[OffsetAnimation, ...] = ()

    def __post_init__(self) -> None:
        if self.component not in ("both", "fill", "glow"):
            raise ValueError("text layer component must be both, fill or glow")
        if self.component == "glow" and self.paint.glow is None:
            raise ValueError("glow-only layer requires a glow paint")
        if not self.source_id or type(self.order) is not int:
            raise ValueError("text layer requires a source id and integer order")
        if self.origin is not None and not isinstance(self.origin, EventOrigin):
            raise TypeError("text layer origin must be EventOrigin or None")
        object.__setattr__(self, "animations", tuple(self.animations))
        object.__setattr__(self, "offsets", tuple(self.offsets))
        for index, motion in enumerate(self.offsets):
            if not isinstance(motion, OffsetAnimation):
                raise TypeError("offsets requires OffsetAnimation")
            for previous in self.offsets[:index]:
                if previous.axis != motion.axis:
                    continue
                start = max(
                    previous.points[0][0], motion.points[0][0], self.window.start_ms
                )
                end = min(
                    self.window.end_ms,
                    self.window.end_ms if previous.keep else previous.points[-1][0],
                    self.window.end_ms if motion.keep else motion.points[-1][0],
                )
                if start < end:
                    raise ValueError(
                        f"{self.source_id}: overlapping {motion.axis} offset animations"
                    )

        object.__setattr__(self, "opacity_animations", tuple(self.opacity_animations))
        for index, motion in enumerate(self.opacity_animations):
            if not isinstance(motion, OpacityAnimation):
                raise TypeError("opacity_animations requires OpacityAnimation")
            for previous in self.opacity_animations[:index]:
                if previous.component != motion.component:
                    continue
                start = max(
                    previous.points[0][0], motion.points[0][0], self.window.start_ms
                )
                end = min(
                    self.window.end_ms,
                    self.window.end_ms if previous.keep else previous.points[-1][0],
                    self.window.end_ms if motion.keep else motion.points[-1][0],
                )
                if start < end:
                    raise ValueError(
                        f"{self.source_id}: overlapping {motion.component} opacity animations"
                    )

        if self.clips is not None:
            object.__setattr__(self, "clips", tuple(self.clips))
            for a, b in pairwise(self.clips):
                if a.end_ms > b.start_ms:
                    raise ValueError(
                        f"{self.source_id}: overlapping or reversed clip spans"
                    )
        self.fade.opacity_at(self.window.start_ms, self.fade_window or self.window)
        for a, b in pairwise(sorted(self.animations, key=lambda a: a.start_ms)):
            if a.end_ms > b.start_ms:
                raise ValueError(f"{self.source_id}: overlapping scale animations")

    @property
    def pass_count(self) -> int:
        """Number of paint passes emitted for each compiled interval."""
        return int(self.component != "glow") + int(
            self.component != "fill" and self.paint.glow is not None
        )


@dataclass(frozen=True)
class OutputSettings:
    resolution: tuple[int, int] = (1920, 1080)
    max_events: int = 10000
    clip_error_px: float = 0.25

    def __post_init__(self) -> None:
        if len(self.resolution) != 2 or any(
            type(v) is not int or v <= 0 for v in self.resolution
        ):
            raise ValueError("resolution must contain two positive integers")
        if type(self.max_events) is not int or self.max_events <= 0:
            raise ValueError("max_events must be positive")
        _finite(self.clip_error_px, "clip error")
        if self.clip_error_px <= 0:
            raise ValueError("clip_error_px must be positive")


@dataclass(frozen=True)
class CompiledLayers:
    events: tuple[Line, ...]
    diagnostics: tuple[str, ...]
    origins: tuple[EventOrigin | None, ...] = ()


def _offset(layer, time, axis, *, left=False):
    for motion in layer.offsets:
        if motion.axis != axis:
            continue
        points = tuple((quantize(t), value) for t, value in motion.points)
        start, end = points[0][0], points[-1][0]
        if time < start or (time == start and left):
            continue
        if time > end or (time == end and not left) or start == end:
            if motion.keep:
                return points[-1][1]
            continue
        return next(
            a + (b - a) * (time - t0) / (t1 - t0)
            for (t0, a), (t1, b) in pairwise(points)
            if t0 <= time <= t1 and t0 < t1
        )
    return 0.0


def _transform(layer, time, *, left=False):
    dx, dy = _offset(layer, time, "x", left=left), _offset(layer, time, "y", left=left)
    for animation in layer.animations:
        points = tuple((quantize(t), value) for t, value in animation.points)
        start, end = points[0][0], points[-1][0]
        if time < start or (time == start and left):
            continue
        if time > end or (time == end and not left):
            if not animation.keep:
                continue
            scale = points[-1][1]
        elif start == end:
            scale = points[-1][1] if animation.keep else 1.0
        else:
            scale = next(
                a + (b - a) * (time - t0) / (t1 - t0)
                for (t0, a), (t1, b) in pairwise(points)
                if t0 <= time <= t1 and t0 < t1
            )
        px, py = animation.pivot
        x, y = (
            px + (layer.box.center - px) * scale,
            py + (layer.box.middle - py) * scale,
        )
        return scale, x + dx, y + dy, px
    return 1, layer.box.center + dx, layer.box.middle + dy, layer.box.center


def _animated_opacity(layer, time, *, glow, left=False):
    group_value = 1.0
    glow_value = layer.paint.glow.opacity if layer.paint.glow is not None else 1.0
    for animation in layer.opacity_animations:
        points = tuple((quantize(t), value) for t, value in animation.points)
        start, end = points[0][0], points[-1][0]
        if time < start or (time == start and left):
            continue
        if time > end or (time == end and not left) or start == end:
            if not animation.keep:
                continue
            value = points[-1][1]
        else:
            value = next(
                a + (b - a) * (time - t0) / (t1 - t0)
                for (t0, a), (t1, b) in pairwise(points)
                if t0 <= time <= t1 and t0 < t1
            )
        if animation.component == "group":
            group_value = value
        else:
            glow_value = value
    return layer.paint.opacity * group_value * (glow_value if glow else 1.0)


def _mask(layer, span, time, *, left=False):
    start, end = quantize(span.start_ms), quantize(span.end_ms)
    t = min(1, max(0, (time - start) / (end - start)))
    region = Region(
        span.start.left + (span.end.left - span.start.left) * t,
        span.start.right + (span.end.right - span.start.right) * t,
    )
    scale, _, _, pivot = _transform(layer, time, left=left)
    dx = _offset(layer, time, "x", left=left)
    return Region(
        pivot + (region.left - pivot) * scale + dx,
        pivot + (region.right - pivot) * scale + dx,
    )


def native_opacity_supported(layer: TextLayer) -> bool:
    """Check known alpha curves without output generation or user callbacks."""
    window = layer.fade_window or layer.window
    knots = {
        quantize(layer.window.start_ms),
        quantize(layer.window.end_ms),
        quantize(window.start_ms),
        quantize(window.end_ms),
        quantize(window.start_ms + layer.fade.in_ms),
        quantize(window.end_ms - layer.fade.out_ms),
    }
    for motion in layer.opacity_animations:
        times = tuple(quantize(t) for t, _ in motion.points)
        if motion.points[-1][0] > motion.points[0][0] and any(
            a >= b for a, b in pairwise(times)
        ):
            return False
        knots.update(times)
    for start, end in pairwise(sorted(knots)):
        if end <= quantize(layer.window.start_ms) or start >= quantize(
            layer.window.end_ms
        ):
            continue
        for glow in (False, True):
            if (glow and (layer.component == "fill" or layer.paint.glow is None)) or (
                not glow and layer.component == "glow"
            ):
                continue

            def at(time, *, left=False, is_glow=glow):
                return _animated_opacity(
                    layer, time, glow=is_glow, left=left
                ) * layer.fade.opacity_at(time, window)

            first, last = at(start), at(end, left=True)
            for fraction in (0.25, 0.5, 0.75):
                if (
                    abs(
                        at(start + (end - start) * fraction)
                        - (first + (last - first) * fraction)
                    )
                    > 1e-10
                ):
                    return False
    return True


def _clip(region, height):
    # libass parses rectangular clip coordinates as integers, even when decimal
    # text is supplied. Round explicitly; this adds at most .5px to curve error.
    return rf"\clip({floor(region.left + 0.5)},0,{floor(region.right + 0.5)},{height})"


def _compile_interval(layer, span, start, end, settings, events):
    emitted_start, emitted_end = start, end
    if layer.active_window is not None:
        emitted_start = max(start, quantize(layer.active_window.start_ms))
        emitted_end = min(end, quantize(layer.active_window.end_ms))
    if emitted_end <= emitted_start:
        return
    # On each curve/animation section, transformed mask edges are quadratic.
    # Linear interpolation's maximum error is at the midpoint. Subdivide only
    # when necessary; static/ordinary sweeps never become frame-sized events.
    first = last = None
    if span is not None:
        first, last = _mask(layer, span, start), _mask(layer, span, end, left=True)
        middle = _mask(layer, span, (start + end) / 2)
        error = max(
            abs(middle.left - (first.left + last.left) / 2),
            abs(middle.right - (first.right + last.right) / 2),
        )
        if error > settings.clip_error_px:
            split = quantize((start + end) / 2)
            if split <= start or split >= end:
                raise OutputCapabilityError(
                    f"{layer.source_id}: transformed clip exceeds {settings.clip_error_px}px at ASS time resolution",
                    origin=layer.origin,
                    time_ms=start,
                )
            _compile_interval(layer, span, start, split, settings, events)
            _compile_interval(layer, span, split, end, settings, events)
            return
        if not first.width and not last.width:
            return
    # Clip approximation cuts are exposures, not new animation knots. Keeping
    # native endpoints also avoids raster/blur changes caused by re-anchoring
    # transforms to a short interval even when the mathematical line is equal.
    geometry_start, geometry_end = start, end
    for animation in layer.animations:
        knots = tuple(quantize(t) for t, _ in animation.points)
        for a, b in pairwise(knots):
            if a <= start < end <= b:
                geometry_start, geometry_end = a, b
                break
    s0, x0, y0, _ = _transform(layer, geometry_start)
    s1, x1, y1, _ = _transform(layer, geometry_end, left=True)
    local_start, local_end = start - emitted_start, end - emitted_start
    geometry_local_start = geometry_start - emitted_start
    geometry_local_end = geometry_end - emitted_start
    position_start, position_end = geometry_start, geometry_end
    if layer.offsets:
        position_knots = {
            quantize(layer.window.start_ms),
            quantize(layer.window.end_ms),
            *(
                quantize(t)
                for motion in (*layer.animations, *layer.offsets)
                for t, _ in motion.points
            ),
        }
        position_start = max(t for t in position_knots if t <= start)
        position_end = min(t for t in position_knots if t >= end)
        _, x0, y0, _ = _transform(layer, position_start)
        _, x1, y1, _ = _transform(layer, position_end, left=True)
    position = (
        rf"\pos({number(x0)},{number(y0)})"
        if (x0, y0) == (x1, y1)
        else rf"\move({number(x0)},{number(y0)},{number(x1)},{number(y1)},{position_start - emitted_start},{position_end - emitted_start})"
    )
    common = r"\an5\q2\shad0" + rf"\fs{number(layer.style.fontsize)}" + position
    common += rf"\fscx{number(layer.style.scale_x * s0)}\fscy{number(layer.style.scale_y * s0)}"
    transform = ""
    if s0 != s1:
        transform += rf"\fscx{number(layer.style.scale_x * s1)}\fscy{number(layer.style.scale_y * s1)}"
    if span is not None:
        if not layer.animations and not any(m.axis == "x" for m in layer.offsets):
            # Preserve the original integer clip endpoints across event cuts.
            # Re-rounding a sampled endpoint changes the sweep by a pixel.
            # libass accepts negative transform times relative to this event.
            common += _clip(span.start, settings.resolution[1])
            if span.start != span.end:
                a = quantize(span.start_ms) - emitted_start
                b = quantize(span.end_ms) - emitted_start
                common += rf"\t({a},{b},1,{_clip(span.end, settings.resolution[1])})"
        else:
            assert first is not None and last is not None
            common += _clip(first, settings.resolution[1])
            if first != last:
                common += rf"\t({local_start},{local_end},1,{_clip(last, settings.resolution[1])})"
    paint = layer.paint
    passes = (
        [(1, paint.fill, paint.outline, paint.border, 0, paint.opacity)]
        if layer.component != "glow"
        else []
    )
    if layer.component != "fill" and paint.glow is not None:
        glow = paint.glow
        passes.insert(
            0,
            (
                0,
                glow.color,
                glow.color,
                glow.border,
                glow.blur,
                paint.opacity * glow.opacity,
            ),
        )
    # Quantize opacity once at the original fade endpoints; re-quantizing it at
    # every clip cut produces different alpha curves on adjacent regions.
    fade_start, fade_end = start, end
    fade_window = layer.fade_window or layer.window
    for a, b in (
        (fade_window.start_ms, fade_window.start_ms + layer.fade.in_ms),
        (fade_window.end_ms - layer.fade.out_ms, fade_window.end_ms),
    ):
        a, b = quantize(a), quantize(b)
        if a <= start < end <= b:
            fade_start, fade_end = a, b
            break
    if layer.opacity_animations:
        # Use original alpha knots, independently of clip and geometry cuts.
        # Re-quantizing alpha at clip cuts would create seams between regions.
        alpha_knots = {
            quantize(layer.window.start_ms),
            quantize(layer.window.end_ms),
            quantize(fade_window.start_ms),
            quantize(fade_window.end_ms),
            quantize(fade_window.start_ms + layer.fade.in_ms),
            quantize(fade_window.end_ms - layer.fade.out_ms),
            *(
                quantize(t)
                for motion in layer.opacity_animations
                for t, _ in motion.points
            ),
        }
        fade_start = max(t for t in alpha_knots if t <= start)
        fade_end = min(t for t in alpha_knots if t >= end)
    for sublayer, fill, outline, border, blur, opacity in passes:
        if layer.opacity_animations:

            def value_at(time, *, left=False, is_glow=sublayer == 0):
                return _animated_opacity(
                    layer, time, glow=is_glow, left=left
                ) * layer.fade.opacity_at(time, fade_window)

            value0, value1 = value_at(fade_start), value_at(fade_end, left=True)
            # Products of fade/group/glow linear ramps can be cubic. Check
            # enough interior points to reject nonlinear products instead of
            # silently emitting an incorrect linear ASS transform.
            for fraction in (0.25, 0.5, 0.75):
                actual = value_at(fade_start + (fade_end - fade_start) * fraction)
                expected = value0 + (value1 - value0) * fraction
                if abs(actual - expected) > 1e-10:
                    raise OutputCapabilityError(
                        f"{layer.source_id}: nonlinear opacity product requires sampling",
                        origin=layer.origin,
                        time_ms=fade_start,
                    )
            a0, a1 = alpha(value0), alpha(value1)
        else:
            a0 = alpha(opacity * layer.fade.opacity_at(fade_start, fade_window))
            a1 = alpha(opacity * layer.fade.opacity_at(fade_end, fade_window))
        tags = (
            common
            + rf"\bord{number(border * s0)}\blur{number(blur * s0)}\1c{color(fill)}\3c{color(outline)}\alpha{a0}"
        )
        change = transform
        if s0 != s1:
            change += rf"\bord{number(border * s1)}\blur{number(blur * s1)}"
        if change:
            tags += rf"\t({geometry_local_start},{geometry_local_end},1,{change})"
        if a0 != a1:
            tags += rf"\t({fade_start - emitted_start},{fade_end - emitted_start},1,\alpha{a1})"
        if len(events) >= settings.max_events:
            raise OutputCapabilityError(
                f"{layer.source_id}: event limit {settings.max_events} exceeded while compiling clip/scale intervals",
                origin=layer.origin,
                time_ms=start,
            )
        events.append(
            Line(
                text="{" + tags + "}" + escape_text(layer.text),
                start_time=emitted_start,
                end_time=emitted_end,
                style=layer.style.name,
                layer=layer.order * 2 + sublayer,
                effect="karaoke:generated:" + layer.source_id,
            )
        )


DEFAULT_OUTPUT_SETTINGS = OutputSettings()


def compile_layers(
    layers: Iterable[TextLayer], *, settings: OutputSettings = DEFAULT_OUTPUT_SETTINGS
) -> CompiledLayers:
    events, diagnostics = [], []
    origins = {}
    for layer in layers:
        if not layer.text.strip():
            continue
        window = layer.window
        start, end = quantize(window.start_ms), quantize(window.end_ms)
        # Subdivide the original timeline before cropping a sampled exposure.
        # Sampling must not move the native curve's approximation/rounding knots.
        if end <= start:
            diagnostics.append(
                f"{layer.source_id}: display window vanished during centisecond quantization"
            )
            continue
        fade_window = layer.fade_window or window
        knots = {
            start,
            end,
            quantize(fade_window.start_ms),
            quantize(fade_window.end_ms),
            quantize(fade_window.start_ms + layer.fade.in_ms),
            quantize(fade_window.end_ms - layer.fade.out_ms),
        }
        for animation in layer.animations:
            times = tuple(quantize(t) for t, _ in animation.points)
            if animation.end_ms > animation.start_ms and any(
                a >= b for a, b in pairwise(times)
            ):
                raise OutputCapabilityError(
                    f"{layer.source_id}: "
                    + (
                        "pulse rise/fall collapses"
                        if animation.keyframes is None
                        else "scale keyframes collapse"
                    )
                    + " at centisecond resolution",
                    origin=layer.origin,
                    time_ms=animation.start_ms,
                )
            knots.update(times)
        for motion in layer.opacity_animations:
            times = tuple(quantize(t) for t, _ in motion.points)
            if motion.points[-1][0] > motion.points[0][0] and any(
                a >= b for a, b in pairwise(times)
            ):
                raise OutputCapabilityError(
                    f"{layer.source_id}: opacity keyframes collapse at centisecond resolution",
                    origin=layer.origin,
                    time_ms=motion.points[0][0],
                )
            knots.update(times)
        for motion in layer.offsets:
            times = tuple(quantize(t) for t, _ in motion.points)
            if motion.points[-1][0] > motion.points[0][0] and any(
                a >= b for a, b in pairwise(times)
            ):
                raise OutputCapabilityError(
                    f"{layer.source_id}: offset keyframes collapse at centisecond resolution",
                    origin=layer.origin,
                    time_ms=motion.points[0][0],
                )
            knots.update(times)
        if layer.clips is not None:
            for span in layer.clips:
                knots.update((quantize(span.start_ms), quantize(span.end_ms)))
                if quantize(span.start_ms) == quantize(span.end_ms):
                    diagnostics.append(
                        f"{layer.source_id}: clip interval vanished during centisecond quantization"
                    )
        knots = sorted(t for t in knots if start <= t <= end)
        for a, b in pairwise(knots):
            span = None
            if layer.clips is not None:
                span = next(
                    (
                        s
                        for s in layer.clips
                        if quantize(s.start_ms) <= a and quantize(s.end_ms) >= b
                    ),
                    None,
                )
                if span is None:
                    continue
            previous = len(events)
            _compile_interval(layer, span, a, b, settings, events)
            for event in events[previous:]:
                origins[id(event)] = layer.origin
    # ASS ReadOrder breaks ties within a layer. Keep source order stable when
    # sampling changes event start times or merges contiguous exposures.
    events.sort(key=lambda event: (event.layer, event.effect, event.start_time))
    return CompiledLayers(
        tuple(events), tuple(diagnostics), tuple(origins[id(e)] for e in events)
    )
