"""A complete, configurable karaoke animation recipe using ordinary Scene objects."""

from collections.abc import Callable, Iterator
from dataclasses import dataclass, replace
from functools import partial
from itertools import groupby, pairwise
from math import ceil, floor, pi, pow, sin, sqrt
from typing import Literal, get_args

from ._contour_stroke import contour_stroke
from ._karaoke_motion import (
    HALO_STROKES,
    ZoomScale,
    glow_scale,
    stretch,
    transition,
    zoom_pulse,
)
from ._karaoke_sprites import (
    _ParticlePaint,
    _ParticleTint,
    ornament,
    painted_particle,
    star_burst,
)
from .appearance import _DEFAULT_SUNG, _DEFAULT_UNSUNG, _EMPTY_THEME, KaraokeTheme
from .composition import Color, Glow, SecondaryOutline
from .document_text import SingingSpan
from .geometry import Vec2, finite
from .lyric_highlights import (
    HighlightArrival,
    LyricGlow,
    LyricGradient,
    LyricHighlights,
    LyricMaterial,
    _hard_glow_border,
    _resolve_material,
    _style_material,
)
from .lyric_line import (
    LyricLine,
    LyricRule,
    LyricTarget,
    _line_x,
)
from .model import Box
from .paint_fields import (
    ColorRamp,
    ColorStop,
    LinearGradient,
    PaintField,
    _mix,
)
from .parameters import Glyph, LengthExpr, _width
from .particles import ParticleContext
from .scene import (
    Lifetime,
    ObjectGroup,
    PathObject,
    RectangleClip,
    RectangleKeyframes,
    SceneObject,
    TextObject,
    _ColorStripClip,
)
from .scene_animation import (
    ScalePulse,
    ShaderMotion,
    StatePatch,
    TimeSpan,
    Transform,
    VisualState,
    linear_rate,
    local_seconds,
    smooth_rate,
)
from .text_geometry import outline_text


def _outline_for(fill: Color) -> Color:
    # Relative sRGB luminance at the black/white contrast crossover.
    def linear(channel: int) -> float:
        value = channel / 255
        return value / 12.92 if value <= 0.04045 else pow((value + 0.055) / 1.055, 2.4)

    luminance = 0.2126 * linear(fill.red) + 0.7152 * linear(fill.green) + 0.0722 * linear(fill.blue)
    neutral = Color(20, 17, 24) if luminance >= 0.179 else Color(255, 248, 236)
    return _mix(fill, neutral, 0.82)



type KaraokeEntry = Literal[
    "none",
    "fade",
    "slide_in",
    "rise",
    "char_fade",
    "char_drip",
    "spin_flip",
    "utopia",
    "tilt_pop",
    "tracking_in",
    "wave_in",
    "stretch_in",
    "glow_in",
    "assemble_in",
    "sparkle",
    "ripple",
    "note",
    "petal",
    "snow",
    "snow_solid",
]
type KaraokeExit = Literal[
    "none",
    "fade",
    "slide_out",
    "rise",
    "char_fade",
    "char_drip",
    "spin_flip",
    "utopia",
    "scatter_out",
    "converge_out",
    "stretch_out",
    "glow_out",
    "dissolve_out",
    "sparkle",
    "ripple",
    "note",
    "petal",
    "snow",
    "snow_solid",
]
type KaraokeSinging = Literal[
    "none",
    "no_wipe",
    "utopia",
    "scanline",
    "utopia_scanline",
    "zoom_pulse",
    "zoom_pulse_scanline",
]
type KaraokeDecoration = Literal[
    "none",
    "twinkle",
    "twinkle_classic",
    "note",
    "ripple",
    "petal",
    "snow",
    "snow_solid",
]
# Per sung glyph, independent of note length: (lifetime in seconds, particle count).
_SING_BURSTS = {
    "ripple": (0.60, 3),
    "twinkle": (0.70, 7),
    "twinkle_classic": (0.70, 3),
    "note": (0.80, 3),
    "petal": (0.90, 4),
    "snow": (1.10, 4),
    "snow_solid": (1.10, 4),
}
# Transition particles per burst. Sparkle spans the whole lyric line.
_TRANSITION_COUNTS = {
    "sparkle": 14,
    "assemble_in": 7,
    "dissolve_out": 7,
    "ripple": 3,
    "note": 3,
    "petal": 3,
    "snow": 3,
    "snow_solid": 3,
}


def _walk(node: SceneObject) -> Iterator[SceneObject]:
    yield node
    if isinstance(node, ObjectGroup):
        for child in node.children:
            yield from _walk(child)


def _insert(
    line: LyricLine, additions: dict[str, list[SceneObject]], *, reserve: bool = True,
    replacements: dict[str, TextObject] | None = None,
) -> LyricLine:
    if not additions and not replacements:
        return line
    windows = tuple(
        TimeSpan(node.lifetime.start, node.lifetime.end)
        for nodes in additions.values()
        for node in nodes
        if reserve and node.lifetime != line.lifetime
    )

    def visit(node: SceneObject) -> SceneObject:
        if not isinstance(node, ObjectGroup):
            return replacements.get(node.id, node) if replacements else node
        return replace(
            node,
            children=tuple(
                item
                for child in node.children
                for item in (visit(child), *additions.get(child.id, ()))
            ),
        )

    result = visit(line)
    assert isinstance(result, LyricLine)
    if not windows:
        return result
    result = result.with_display(
        Lifetime(
            min(result.lifetime.start, *(s.start for s in windows)),
            max(result.lifetime.end, *(s.end for s in windows)),
        )
    )
    return replace(result, required_display=(*result.required_display, *windows))


def _stretch_halo(
    node: TextObject,
    em: float,
    pivot: Vec2,
    prefix: str,
    entering: bool,
    birth: float,
    duration: float,
    shine: Color,
) -> Iterator[TextObject]:
    path = outline_text(node).path
    if path is None:
        return
    paint = contour_stroke(path, 0.75 * em * max(width for width, _ in HALO_STROKES))
    motion = stretch(entering, pivot)
    for width, strength in HALO_STROKES:

        def sample(base: VisualState, p: float, pen: float = width) -> VisualState:
            q = smooth_rate(p)
            radius = 1.2 - 0.5 * q if entering else 0.7 + 0.8 * q
            intensity = (1 - q) ** 1.5 if entering else 0.9 * sin(pi * q)
            moved = motion.sample(base, p)
            return replace(
                moved,
                border=em * pen * radius / 2,
                opacity=moved.opacity * intensity,
            )

        copy = replace(
            node,
            id=f"{prefix}:{width}",
            shader_paint=paint,
            scale_border=True,
            filled=False,
            layer=node.layer - 1,
            lifetime=Lifetime(birth, birth + duration),
            clock_start=birth,
            animations=(),
            material=None,
            reference=None,
            clip=None,
            state=replace(
                node.state,
                fill=shine,
                outline=shine,
                border=0,
                blur=0,
                shadow=Vec2(),
                opacity=node.state.opacity * strength,
            ),
        )
        yield copy.animate(
            replace(motion, function=sample, channels=motion.channels | {"border"},
                    parameters=(*motion.parameters, em*width/2),
                    source=motion.source + """
                        pen=item(data+3)*(entering?1.2-0.5*q:0.7+0.8*q);
                        alpha*=entering?pow(1.-q,1.5):0.9*sin(3.14159265*q);
                    """),
            duration=duration,
        )


@dataclass(frozen=True)
class _Burst:
    target: LyricTarget
    glyph_index: int
    node: TextObject
    kind: str
    start: float
    duration: float
    count: int
    phase: Literal["entry", "exit", "singing"]


def _burst_seed(kind: str, entering: bool, exiting: bool) -> int:
    if not entering and not exiting:
        return 5
    entry, exit = {
        "ripple": (2, 4),
        "note": (6, 8),
        "assemble_in": (7, 9),
        "dissolve_out": (7, 9),
        "petal": (10, 11),
        "snow": (12, 13),
        "snow_solid": (12, 13),
    }[kind]
    return entry if entering else exit


def _transition_burst(
    kind: str,
    total: float,
    entering: bool,
    display: Lifetime,
    sung_end: float,
    stagger: float,
    index: int,
    count: int,
) -> tuple[float, float]:
    """Absolute particle birth and full motion duration, prior to display clipping."""
    # Studio schedules particle births in integer milliseconds, quantizing
    # the inter-character step before scaling it to the configured duration.
    window = max(1, round(total * 1000))
    scale = window / 600
    start, end = round(display.start * 1000), round(display.end * 1000)
    done = round(sung_end * 1000)
    if kind == "sparkle":
        if entering:
            return start / 1000, int(700 * scale) / 1000
        birth = min(end - 120, max(done, end - window))
        return birth / 1000, (end - birth) / 1000
    if kind in {"snow", "snow_solid"}:
        if entering:
            birth = start - int(200 * scale)
            finish = start + window + int(250 * scale)
        else:
            birth = max(done, end - window)
            finish = end + int(300 * scale)
        return birth / 1000, (finish - birth) / 1000

    spread = 600 * stagger
    gaps = max(1, count - 1)
    step = int((spread // gaps) * scale)
    life = {
        "petal": 900, "note": 800, "ripple": 600, "assemble_in": 320, "dissolve_out": 320,
    }[kind]
    travel = max(1, int(life * scale))
    if not entering:
        start = max(done, end - int((spread + life) * scale))
        if kind != "dissolve_out":
            start = min(start, end - 120)
        step = min(step, max(0, end - start - travel) // gaps)
        if kind == "ripple":
            # Studio's exit ring emitter scales the compressed step once more.
            step = int(step * scale)
    return (start + index * step) / 1000, travel / 1000


_CHAR_TRANSITIONS = {"char_fade", "char_drip", "spin_flip"}


def _character_hosts(line: LyricLine) -> dict[str, LyricTarget]:
    """Map each displayed glyph to the main character that leads its transition."""
    targets = line.query("character")
    by_offset = {g.start: t for g, t in zip(line.layout.body.characters, targets, strict=True)}
    hosts = {t.node_id: t for t in targets}
    readings = (r for r in line.layout.ruby for _ in r.layout.characters)
    hosts.update((t.node_id, by_offset[r.body_start])
                 for t, r in zip(line.query("ruby"), readings, strict=True))
    return hosts


def _reading_edges(line: LyricLine) -> dict[str, tuple[float, float]]:
    """Express the whole annotation's horizontal bounds in each kana's local coordinates."""
    bounds: dict[int, tuple[float, float]] = {}
    for r in line.layout.ruby:
        if r.unit_index not in bounds:
            body = line.layout.body.range_bounds(r.body_start, r.body_end)
            bounds[r.unit_index] = body.left, body.right
        left, right = bounds[r.unit_index]
        bounds[r.unit_index] = min(left, r.layout.bounds.left), max(right, r.layout.bounds.right)

    result = {}
    readings = ((r, g) for r in line.layout.ruby for g in r.layout.characters)
    for target, (reading, glyph) in zip(line.query("ruby"), readings, strict=True):
        result[target.node_id] = _line_x(glyph, *bounds[reading.unit_index])
    return result


def _character_offsets(line: LyricLine, hosts: dict[str, LyricTarget], spread: float,
                       *, entering: bool, individual: bool = False) -> dict[str, float]:
    if individual:
        offsets = {}
        for role in ("character", "ruby"):
            glyphs = line.query(role)
            for i, glyph in enumerate(glyphs):
                phase = i if entering else i + 1 - len(glyphs)
                offsets[glyph.node_id] = (phase / max(1, len(glyphs) - 1)) * spread
        return offsets
    targets = line.query("character")
    step = round(spread * 1000) // max(1, len(targets) - 1) / 1000
    offsets = {t.node_id: (i if entering else i + 1 - len(targets)) * step
               for i, t in enumerate(targets)}
    return {key: offsets[host.node_id] for key, host in hosts.items()}


def _utopia_exit_anchor(line: LyricLine, duration: float, release: float) -> Callable[[LyricLine, LyricTarget], tuple[TimeSpan, ...]]:
    """Leave after the next visible main character finishes, including for its preceding reading."""
    glyphs = tuple(line._glyph_regions(automatic=False))
    last = max((s.end + target.delay for target in line.query("character") for s in target.singing),
               default=line.lifetime.end)
    tail = max(0, line.lifetime.end - last - duration)
    annotated = {reading.unit_index for reading in line.layout.ruby}
    departures: dict[str, float] = {}
    group_ends: dict[int, float] = {}
    following = None
    for target, glyph, unit, _ in reversed(glyphs):
        if target.role != "character" or not target.singing:
            continue
        done = max(s.end for s in target.singing) + target.delay
        at = following if following is not None and following >= done else done + tail
        at = max(done + release, at)
        if unit in annotated:
            at = group_ends.setdefault(unit, at)
        departures[target.node_id] = at
        if glyph.object.text.strip():
            following = done
    for target, _, unit, _ in glyphs:
        if target.role == "ruby" and unit in group_ends:
            departures[target.node_id] = group_ends[unit]
    def anchor(_line: LyricLine, target: LyricTarget) -> tuple[TimeSpan, ...]:
        at = departures.get(target.node_id)
        return () if at is None else (TimeSpan(at, at),)

    return anchor


def _display_start(line: LyricLine, _target: LyricTarget) -> tuple[TimeSpan, ...]:
    return (TimeSpan(line.lifetime.start, line.lifetime.start),)


def _transition_window(kind: str, configured: float, *, entering: bool) -> float:
    if kind == "none" or configured == 0:
        return 0
    if kind in {"utopia", "tilt_pop"}:
        return 0.70 if entering else 0.75
    if kind in _CHAR_TRANSITIONS:
        return 0.60
    if kind in {"fade", "slide_in", "slide_out", "rise"}:
        return configured
    return min(3, max(0.12, configured))


def _utopia(duration: float, target: LyricTarget) -> ScalePulse:
    attack_ms = min(round(duration * 1000) // 4, 100)
    return ScalePulse(
        peak=1.15 if attack_ms else 1,
        peak_at=attack_ms / (1000 * duration) if attack_ms else 0.5,
        rate=linear_rate,
        pivot=target._baseline_pivot,
    )


@dataclass(frozen=True)
class _SingingPulse:
    note: TimeSpan
    duration: float
    animation: ScalePulse | Transform

    def rule(self, target: LyricTarget, resume: float | None) -> LyricRule | None:
        skip = max(0.0, (resume or 0.0) - self.note.start)
        if skip >= self.duration:
            return None

        def anchor(_line: LyricLine, _target: LyricTarget) -> tuple[TimeSpan, ...]:
            return (self.note,)

        animation = self.animation
        remaining: ShaderMotion | Transform | ScalePulse = animation
        if skip:
            pivot = animation.pivot or Vec2()
            if isinstance(animation, ScalePulse):
                # Utopia's attack/release is linear on either side of peak_at.
                body = "float k=min(p/item(data+2),(1.-p)/(1.-item(data+2))); float factor=mix(1.,item(data+3),k);"
                parameters = (pivot.x, pivot.y, animation.peak_at, animation.peak)
            else:
                zoom = animation.scale
                assert isinstance(zoom, ZoomScale)
                body = """
                    float t=p*item(data+3), note=item(data+2);
                    float d=t<=note?1.-t/note:min(1.,(t-note)/0.30);
                    float factor=1.+0.10*(1.-pow(clamp(d,0.,1.),item(data+4)));
                """
                parameters = (pivot.x, pivot.y, zoom.note, zoom.duration, zoom.exponent)
            remaining = ShaderMotion(
                animation.sample, animation.channels,
                body + """
                    mat2 before=basisOf(scale,skew,angle);
                    scale*=factor;
                    pos+=(before-basisOf(scale,skew,angle))*pairAt(data);
                """, parameters, progress_offset=skip/self.duration,
                progress_scale=1-skip/self.duration,
            )
        return LyricRule(
            target, anchor, remaining,
            duration=self.duration - skip, offset=skip, hold=isinstance(self.animation, ScalePulse),
        )

    def inverse_scale(self, elapsed: float) -> float:
        progress = min(1.0, max(0.0, elapsed / self.duration)) if self.duration else 0.0
        return 1 / self.animation.sample(VisualState(), progress).scale.x

    def band_knots(self, width: float) -> Iterator[float]:
        """Split the reciprocal scale curve when a strip edge drifts over a quarter pixel."""
        peak = (self.duration * self.animation.peak_at if isinstance(self.animation, ScalePulse)
                else self.note.duration)

        def refine(a: float, b: float) -> Iterator[float]:
            mid = (a + b) / 2
            error = abs(self.inverse_scale(mid) - (self.inverse_scale(a) + self.inverse_scale(b)) / 2)
            if error * width / 2 > 0.25 and b - a > 0.01:
                yield from refine(a, mid)
                yield self.note.start + mid
                yield from refine(mid, b)

        yield self.note.start
        yield from refine(0, peak)
        yield self.note.start + peak
        yield from refine(peak, self.duration)
        yield self.note.start + self.duration


def _singing_pulses(
    intervals: tuple[TimeSpan, ...], target: LyricTarget, *, zoom: bool, level: int,
) -> tuple[_SingingPulse, ...]:
    pulses = []
    for i, note in enumerate(intervals):
        if zoom:
            gap = intervals[i + 1].start - note.end if i + 1 < len(intervals) else 0.30
            duration = note.duration + max(0, min(0.30, gap))
            motion = zoom_pulse(max(note.duration, 0.001), duration, level, target.center)
        else:
            duration = note.duration
            motion = _utopia(duration, target)
        pulses.append(_SingingPulse(note, duration, motion))
    return tuple(pulses)


def _particle_ink(
    source: LyricMaterial, target: LyricTarget, painted: SceneObject | None, fallback: Color,
) -> _ParticlePaint:
    """Retain the source ramp and Studio's unweighted mean for solid silhouettes."""
    declared = _style_material(source, target.source_style)
    if isinstance(declared, LyricGradient):
        colors = declared.colors
        ramp = ColorRamp(tuple(ColorStop(i / (len(colors) - 1), c) for i, c in enumerate(colors)))
        gradient = LinearGradient(axis=declared.axis, fill=ramp)
    else:
        field = painted.material if painted is not None else None
        if not isinstance(field, LinearGradient):
            return _ParticlePaint(fill=fallback)
        start, end = field.bounds

        def normalized(source: ColorRamp | None) -> ColorRamp | None:
            if source is None:
                return None
            return ColorRamp(tuple(ColorStop((s.position - start) / (end - start), s.color) for s in source.stops))

        gradient = replace(field, fill=normalized(field.fill), outline=normalized(field.outline))
        colors = tuple(s.color for s in field.fill.stops) if field.fill else (fallback,)
    mean = Color(sum(c.red for c in colors) // len(colors),
                 sum(c.green for c in colors) // len(colors),
                 sum(c.blue for c in colors) // len(colors))
    return _ParticlePaint(fill=mean, gradient=gradient)


def _brighten(color: Color, strength: float) -> Color:
    """Raise HSV value toward white while retaining hue and saturation."""
    channels = (color.red, color.green, color.blue)
    value = max(channels)
    raised = value + (255 - value) * strength
    if value == 0:
        return Color(*(round(raised) for _ in channels))
    return Color(*(round(c * raised / value) for c in channels))


def _scanline_run_spans(line: LyricLine) -> dict[str, tuple[float, float]]:
    """Studio repaints the band with the brush box of each contiguous glyph run."""
    spans = {}
    for layout in (line.layout.body, *(r.layout for r in line.layout.ruby)):
        for _, items in groupby(layout.characters, key=lambda g: g.source_style):
            run = tuple(items)
            left = min(g.bounds.left for g in run)
            right = max(g.bounds.right for g in run)
            for glyph in run:
                spans[glyph.object.id] = _line_x(glyph, left, right)
    return spans


def _scanline_brush(
    source: LyricMaterial, target: LyricTarget, span: tuple[float, float] | None,
    fallback: PaintField | None,
) -> PaintField | None:
    selected = _style_material(source, target.source_style)
    if isinstance(selected, LyricGradient) and selected.axis == "x" and span is not None:
        return selected._between(*span)
    return fallback


def _brighten_gradient(material: LinearGradient, strength: float) -> LinearGradient:
    def ramp(colors: ColorRamp | None) -> ColorRamp | None:
        return (
            None
            if colors is None
            else ColorRamp(
                tuple(
                    replace(stop, color=_brighten(stop.color, strength))
                    for stop in colors.stops
                )
            )
        )

    return replace(material, fill=ramp(material.fill), outline=ramp(material.outline))


def _compatible_brushes(*fields: PaintField | None) -> bool:
    axes = set()
    fill_stops: set[float] = set()
    outline_stops: set[float] = set()
    for field in fields:
        if field is None:
            continue
        if not isinstance(field, LinearGradient):
            return False
        axes.add((field.axis, field.space))
        if field.fill:
            fill_stops.update(s.position for s in field.fill.stops)
        if field.outline:
            outline_stops.update(s.position for s in field.outline.stops)
    # A composed brush must also fit the standalone GPU hook's ramp table.
    return len(axes) <= 1 and max(len(fill_stops), len(outline_stops)) <= 16


def _mix_brush(
    base: TextObject,
    fill: Color,
    outline: Color,
    field: PaintField | None,
    strength: float,
) -> PaintField | None:
    """Interpolate aligned linear brushes at every slope change of either ramp."""
    if strength == 1:
        return field
    original = base.material
    settings = original or field
    if settings is None:
        return None
    assert isinstance(settings, LinearGradient)
    assert original is None or isinstance(original, LinearGradient)
    assert field is None or isinstance(field, LinearGradient)

    def ramp(
        first: ColorRamp | None,
        last: ColorRamp | None,
        a: Color,
        b: Color,
    ) -> ColorRamp | None:
        positions = sorted({s.position for r in (first, last) if r for s in r.stops})
        if not positions:
            return None
        return ColorRamp(
            tuple(
                ColorStop(
                    p,
                    _mix(
                        first.at(p) if first else a, last.at(p) if last else b, strength
                    ),
                )
                for p in positions
            )
        )

    return replace(
        settings,
        step=min(g.step for g in (original, field) if g is not None),
        fill=ramp(
            original.fill if original else None,
            field.fill if field else None,
            base.state.fill,
            fill,
        ),
        outline=ramp(
            original.outline if original else None,
            field.outline if field else None,
            base.state.outline,
            outline,
        ),
    )


@dataclass(frozen=True)
class _Sweep:
    start: float
    end: float
    left: float
    right: float

    def after(self, time: float) -> "_Sweep":
        if self.start >= time:
            return self
        progress = (time - self.start) / (self.end - self.start)
        return _Sweep(time, self.end, self.left + (self.right - self.left) * progress, self.right)

    def intersect(self, left: float, right: float) -> "_Sweep | None":
        width = self.right - self.left
        if width == 0:
            return self if left <= self.left <= right else None
        a, b = sorted(((left - self.left) / width, (right - self.left) / width))
        a, b = max(0, a), min(1, b)
        if a >= b:
            return None
        duration = self.end - self.start
        return _Sweep(
            self.start + a * duration, self.start + b * duration,
            self.left + a * width, self.left + b * width,
        )


def _front_clock(
    intervals: set[tuple[float, float]], complete: float | None = None,
) -> tuple[float | None, dict[float, float]]:
    """Keep a moving front visible on its release frame before a rest."""
    notes = sorted(intervals)
    if not notes:
        return None, {}
    first, end = notes[0]
    releases = {}
    for start, stop in notes[1:]:
        if start > end + 1e-9:
            releases[end] = min(start, end + 0.01)
        end = max(end, stop)
    if complete is not None and end < complete:
        releases[end] = min(complete, end + 0.01)
    return first, releases


def _sweeps(
    parts: tuple[tuple[SingingSpan, float, float], ...],
    delay: float,
    bounds: Box,
    previous: tuple[_Sweep, ...],
    first_note: float | None,
    releases: dict[float, float],
    first_pixel: float = 0.5,
    reverse: bool = False,
) -> tuple[_Sweep, ...]:
    if not bounds.width:
        return ()

    sweeps = []
    for span, a, b in parts:
        left, right = bounds.left + bounds.width * a, bounds.left + bounds.width * b
        if reverse:
            left, right = bounds.right - bounds.width * a, bounds.right - bounds.width * b
        start, end = span.start + delay, span.end + delay
        if a == b == 0:
            # A leading empty reading has no painted edge to illuminate.
            if first_note == start:
                first_note = end
            continue
        if end <= start:
            # A checkpoint jump has a release position for the next note.
            # Its zero-width time interval paints no moving band.
            if a > 0 or b < 1:
                sweeps.append(_Sweep(end, end, right, right))
                if end in releases and b == 1:
                    sweeps.append(_Sweep(end, releases[end], right, right))
            continue
        onset, duration = start, end - start

        width = right - left
        arrival = next(
            (s.right for s in reversed(previous) if a == 0 and s.end <= start + 1e-9), left
        )
        if first_note == start and a == 0:
            # fill_clip_band is empty until the first rounded pixel of ink.
            threshold = min(1.0, first_pixel / abs(width))
            ticks = floor(100 * duration * threshold) + 1
            start = min(end, start + ticks / 100)
            left += width * (start - onset) / duration
            arrival = left
        if arrival != left:
            # At a shared boundary or a restart, Studio first displays the
            # preceding endpoint, then advances along the new trajectory.
            join = min(start + 0.01, end)
            x = right - width * (end - join) / duration
            sweeps.append(_Sweep(start, join, arrival, x))
            start, left = join, x
        if start < end:
            sweeps.append(_Sweep(start, end, left, right))
        if end in releases and b == 1:
            sweeps.append(_Sweep(end, releases[end], right, right))
    return tuple(sweeps)


def _front_paths(movements: list[_Sweep]) -> Iterator[list[tuple[float, float]]]:
    """Join touching movements so one moving strip spans the handoff."""
    path: list[tuple[float, float]] = []
    for sweep in sorted(movements, key=lambda s: s.start):
        if sweep.start == sweep.end:
            continue
        if path:
            end, right = path[-1]
            if abs(end - sweep.start) > 1e-9 or abs(right - sweep.left) > 1e-8:
                yield path
                path = []
        if not path:
            path.append((sweep.start, sweep.left))
        path.append((sweep.end, sweep.right))
    if path:
        yield path


type _FrontPath = tuple[tuple[float, float], ...]
type _BandPath = tuple[tuple[float, float, float], ...]


def _band_path(path: _FrontPath, scale_x: float, origin: float,
               pulses: tuple[_SingingPulse, ...], width: float) -> _BandPath:
    """Keep the mapped front on the glyph, but express strip widths in canvas pixels."""
    if not pulses:
        return tuple((t, x, 1 / scale_x) for t, x in path)
    knots = {t for t, _ in path}
    for pulse in pulses:
        for t in pulse.band_knots(width):
            local = local_seconds(t, origin)
            if path[0][0] < local < path[-1][0]:
                knots.add(local)
    result = []
    segments = iter(pairwise(path))
    (a, left), (b, right) = next(segments)
    for t in sorted(knots):
        while t > b:
            (a, left), (b, right) = next(segments)
        x = left if t == a else left + (right - left) * ((t - a) / (b - a))
        inverse = 1.0
        before = None
        for pulse in pulses:
            end = local_seconds(pulse.note.start + pulse.duration, origin)
            if t == end and t > path[0][0]:
                before = pulse.inverse_scale(pulse.duration)
            elapsed = local_seconds(t + origin, pulse.note.start)
            if elapsed >= 0 and t < end:
                inverse = pulse.inverse_scale(elapsed)
                break
        if before is not None and before != inverse:
            # A repeated note can truncate the release and reset at the same instant.
            result.append((t, x, before / scale_x))
            if t == path[-1][0]:
                continue
        result.append((t, x, inverse / scale_x))
    return tuple(result)


@dataclass(frozen=True)
class _ScanlineLayer:
    drawing: TextObject
    sung_brush: PaintField | None
    waiting_brush: PaintField | None
    sides: tuple[TextObject, TextObject] | None


def _hard_rim(node: SceneObject | None, primary_border: float) -> TextObject | None:
    if (
        isinstance(node, TextObject)
        and node.state.blur == 0
        and node.state.border > primary_border
    ):
        return node
    return None


def _hard_rims(
    nodes: dict[str, SceneObject], glyph: SceneObject, sung_id: str,
) -> tuple[TextObject | None, TextObject | None]:
    return (
        _hard_rim(nodes.get(sung_id + "/secondary-outline") or nodes.get(sung_id + "/glow"), glyph.state.border),
        _hard_rim(nodes.get(glyph.id + "/secondary-outline") or nodes.get(glyph.id + "/glow"), glyph.state.border),
    )


def _outside_front(
    piece: TextObject, paths: tuple[_BandPath, ...], offset: float, *, left: bool
) -> TextObject:
    """Keep the ordinary wipe between passes and meet the feather while it moves."""
    clip = piece.clip
    assert isinstance(clip, RectangleClip) and isinstance(
        clip.deform, RectangleKeyframes
    )
    original = clip.deform
    keys = list(original.keyframes)
    for path in paths:
        start, end = path[0][0], path[-1][0]
        keys = [key for key in keys if not start <= key[0] <= end]
        keys.append((start, original.bounds_at(start, before=True)))
        for time, x, per_px in path:
            xmin, t, xmax, b = original.bounds_at(time)
            keys.append(
                (time, (xmin, t, x + offset * per_px, b) if left else (x + offset * per_px, t, xmax, b))
            )
        keys.append((end, original.bounds_at(end)))
    keys.sort(key=lambda key: key[0])
    return replace(piece, clip=replace(clip, deform=RectangleKeyframes(tuple(keys))))


def _clip_rows(piece: TextObject, top: float, bottom: float) -> TextObject:
    """Limit a horizontal singing clip to fixed rows in glyph-local coordinates."""
    clip = piece.clip
    assert isinstance(clip, RectangleClip) and isinstance(clip.deform, RectangleKeyframes)
    return replace(piece, clip=replace(clip, deform=RectangleKeyframes(tuple(
        (t, (left, top, right, bottom)) for t, (left, _, right, _) in clip.deform.keyframes
    ))))


def _fade_underpaint(node: TextObject, start: float) -> TextObject:
    """Studio fades waiting and sung ink independently during a character exit."""
    clip = node.clip
    if not isinstance(clip, RectangleClip) or not isinstance(clip.deform, RectangleKeyframes):
        return node
    t = local_seconds(start, node.time_origin)
    keys = tuple(k for k in clip.deform.keyframes if k[0] < t)
    bounds = clip.deform.bounds_at(t, before=True)
    return replace(node, clip=replace(clip, deform=RectangleKeyframes((
        *keys, (t, bounds), (t, (-65536, -65536, 65536, 65536)),
    ))))


def _scanline_slices(
    width: float, softness: float
) -> Iterator[tuple[float, float, float]]:
    """Disjoint clips across the Studio band, sampled at each strip center."""
    half = width / 2
    softness = min(softness, half)
    if softness == 0:
        yield -half, half, 1.0
        return
    count = min(64, max(1, int(width + 0.5)))
    step = width / count
    def strength(index: int) -> float:
        distance = abs((index + 0.5) * step - half)
        return smooth_rate(min(1, max(0, (half - distance) / softness)))

    # A wide uniform core needs only one moving clip per paint.
    for weight, indices in groupby(range(count), key=strength):
        group = tuple(indices)
        yield group[0] * step - half, (group[-1] + 1) * step - half, weight


@dataclass(frozen=True, kw_only=True)
class KaraokeEffects:
    """Compose entry, singing, exit and ornaments as one Track.effects callable.

    All durations are seconds, widths are script pixels; particle_size is a
    fraction of the shaped font’s em size. Entry/exit duration includes the
    full stagger span. Zero disables that transition. `none` singing retains
    ordinary wipe; `no_wipe` recolors the whole timed unit at completion. Utopia pulses
    within each note; zoom_pulse grows throughout the note and releases over .30 s.
    Ornament tails request display time and follow the host on a dense automatic track.
    material/glow/base_glow use the same factories as LyricHighlights.
    Display-anchored transitions share the time available at a dense row handoff.
    A zoom release can finish early to make room for the exit.
    Overlapping repeats truncate the preceding zoom release and restart its pulse.

    Includes the Studio animation-menu families, independently implemented on
    this engine. It is a visual recipe, not an importer or pixel-identical renderer.
    Use ordinary LyricRule/custom effects alongside it. Apply once per line, before
    another highlight factory; this recipe owns the base/sung appearance and masks.
    secondary_outline adds a solid outer stroke to both states, independently of glow.
    sung_secondary_outline overrides its sung color and width.
    dual_outline derives contrasting outlines for unspecified roles.
    Decorations use seeded glyph-local trajectories; ruby receives text transitions
    and sweeps but not particles or outline flash. max_particles bounds the number
    of particles planned per line, including entry and exit. With particle_layers="stroke",
    following particles inherit the glyph's hard outline radii relative to its em;
    a second hard rim is a separate drawing of the same moving particle.

    ASS supports native clips and eligible transforms. Complex motion, gradients
    and soft fronts raise SceneCompileError on ASS export. Hook export uses
    the same Scene; dynamic blur can require additional cached native coverage.
    No dependency on Manim, Qt, or the reference application is introduced.
    """

    entry: KaraokeEntry = "fade"
    exit: KaraokeExit = "fade"
    singing: KaraokeSinging = "utopia"
    entry_unit: Literal["preset", "character"] = "preset"
    exit_unit: Literal["preset", "character"] = "preset"
    reverse_wipe: bool = False
    decoration: KaraokeDecoration = "none"
    entry_duration: float = 0.3
    exit_duration: float = 0.3
    stagger: float = 7 / 12
    sung: Color | None = None
    unsung: Color | None = None
    material: LyricMaterial = None
    base_material: LyricMaterial = None
    glow: LyricGlow = None
    base_glow: LyricGlow = None
    secondary_outline: SecondaryOutline | None = None
    sung_secondary_outline: SecondaryOutline | None = None
    particle_color: Color | tuple[Color, Color] | Literal["follow_before", "follow_after", "follow_mix", "illustrated"] | None = None
    particle_layers: Literal["solid", "stroke", "decor", "all"] = "solid"
    particle_glow_concentration: int = 0
    particle_size: float = 0.40
    particle_rate: float | None = None
    max_particles: int = 512
    seed: int = 0
    zoom_pulse_curve_level: int = 1
    scanline_width: float | LengthExpr | None = None
    scanline_softness: float | LengthExpr | None = None
    scanline_mode: Literal[
        "color", "brighten", "follow_before", "follow_after", "role"
    ] = "color"
    ruby_reading_units: bool = False
    ruby_scanline: Literal["reading", "both"] = "reading"
    scanline_material: LyricMaterial = None
    scanline_brightness: float = 0.60
    shine: Color | None = None
    scanline_color: Color | None = None
    hook_feather: float | LengthExpr = 0
    front_color: Color | None = None
    unsung_outline: Color | None = None
    sung_outline: Color | None = None
    dual_outline: bool = False
    stroke_flash: bool = False
    id: str = "karaoke"

    @property
    def _secondary_width(self) -> float:
        return max((rim.width for rim in (self.secondary_outline, self.sung_secondary_outline) if rim), default=0)

    @property
    def _hard_border(self) -> float:
        return max(_hard_glow_border(self.base_glow), _hard_glow_border(self.glow))

    @classmethod
    def duotone(
        cls,
        *,
        unsung: Color | None = None,
        unsung_outline: Color | None = None,
        sung: Color | None = None,
        sung_outline: Color | None = None,
        feather: float | LengthExpr = Glyph.font_size / 6,
    ) -> "KaraokeEffects":
        """Wipe between two fill/outline pairs. The moving boundary carries no separate ink."""
        return cls(
            singing="none",
            sung=sung,
            unsung=unsung,
            sung_outline=sung_outline,
            unsung_outline=unsung_outline,
            hook_feather=feather, dual_outline=True,
        )

    def __post_init__(self) -> None:
        for value, choices in (
            (self.entry, KaraokeEntry),
            (self.exit, KaraokeExit),
            (self.singing, KaraokeSinging),
            (self.decoration, KaraokeDecoration),
        ):
            if value not in get_args(choices.__value__):
                raise ValueError(f"unknown karaoke effect: {value}")
        if (
            type(self.zoom_pulse_curve_level) is not int
            or not 0 <= self.zoom_pulse_curve_level <= 5
        ):
            raise ValueError("zoom pulse curve level must be an integer in [0,5]")
        width = 16 if self.scanline_width is None or isinstance(self.scanline_width, LengthExpr) else self.scanline_width
        if any(unit not in {"preset", "character"} for unit in (self.entry_unit, self.exit_unit)):
            raise ValueError("transition unit must be preset or character")
        if self.ruby_scanline not in {"reading", "both"}:
            raise ValueError("ruby_scanline must be reading or both")
        if self.scanline_mode not in {
            "color",
            "brighten",
            "follow_before",
            "follow_after",
            "role",
        }:
            raise ValueError("unknown scanline mode")
        if not 0 <= self.scanline_brightness <= 1:
            raise ValueError("scanline brightness must be in [0,1]")
        if self.scanline_softness is not None and not isinstance(self.scanline_softness, LengthExpr):
            finite(self.scanline_softness)
            if self.scanline_softness < 0:
                raise ValueError("scanline softness must be nonnegative")
        if self.scanline_color is not None and not isinstance(self.scanline_color, Color):
            raise TypeError("scanline_color must be a Color")
        rate = 1 if self.particle_rate is None else self.particle_rate
        finite(
            self.entry_duration,
            self.exit_duration,
            self.stagger,
            self.particle_size,
            rate,
            width,
        )
        if (
            min(self.entry_duration, self.exit_duration) < 0
            or not 0 <= self.stagger < 1
        ):
            raise ValueError("durations must be nonnegative and stagger in [0,1)")
        if not isinstance(self.hook_feather, LengthExpr):
            _width(self.hook_feather, 0, 0, "hook_feather")
        if min(self.particle_size, rate, width) <= 0:
            raise ValueError("particle size/rate and scanline width must be positive")
        if (
            type(self.max_particles) is not int
            or self.max_particles < 1
            or type(self.seed) is not int
        ):
            raise ValueError("particle budget must be positive and seed an integer")
        if (
            not self.id
            or (self.sung is not None and not isinstance(self.sung, Color))
            or (self.unsung is not None and not isinstance(self.unsung, Color))
        ):
            raise ValueError("effects need an id and Color paints")
        if type(self.particle_glow_concentration) is not int or not -1 <= self.particle_glow_concentration <= 2:
            raise ValueError("particle glow concentration must be an integer in [-1,2]")
        if self.particle_layers not in ("solid", "stroke", "decor", "all"):
            raise ValueError("unknown particle paint layers")
        palette = self.particle_color
        if palette is not None and palette not in ("follow_before", "follow_after", "follow_mix", "illustrated") and not isinstance(palette, Color) and not (
            isinstance(palette, tuple) and len(palette) == 2 and all(isinstance(c, Color) for c in palette)
        ):
            raise TypeError("particle_color must be a Color, a pair of colors, a follow mode, or None")

    def with_theme(self, theme: KaraokeTheme = _EMPTY_THEME) -> "KaraokeEffects":
        """Resolve effective color roles, leaving explicit materials and colors in place."""
        sung = self.sung or theme.sung or _DEFAULT_SUNG
        unsung = self.unsung or theme.unsung or _DEFAULT_UNSUNG
        shine = self.shine or theme.shine or _mix(sung, Color(255, 255, 255), 0.80)
        return replace(
            self, sung=sung, unsung=unsung,
            sung_outline=self.sung_outline or theme.sung_outline or (
                _outline_for(sung) if self.dual_outline else None
            ),
            unsung_outline=self.unsung_outline or theme.unsung_outline or (
                _outline_for(unsung) if self.dual_outline else None
            ),
            shine=shine, scanline_color=self.scanline_color or shine,
            particle_color=self.particle_color or "follow_after",
        )

    def __call__(self, line: LyricLine) -> LyricLine:
        """Prepare appearance and defer text motion through the common lyric rules."""
        return self.with_theme()._decorate(line)

    def _decorate(self, line: LyricLine) -> LyricLine:
        if line.layout._vertical:
            # Studio draws the entire column through its line animator. Glyph
            # transitions, scanlines and particles belong to its horizontal painter.
            return replace(
                self,
                entry=self.entry if self.entry in ("fade", "slide_in", "rise") else "none",
                exit=self.exit if self.exit in ("fade", "slide_out", "rise") else "none",
                singing="no_wipe" if self.singing == "no_wipe" else "none",
                decoration="none", stroke_flash=False,
            )._apply(line)
        return self._apply(line)

    def _apply(self, line: LyricLine) -> LyricLine:
        if line.coverage is not None:
            raise ValueError("KaraokeEffects requires ordinary clip-mode lyrics")
        marker = f"/{self.id}:"
        if any(marker in node.id for node in _walk(line)):
            raise ValueError("duplicate karaoke effect id")
        spans = [span for target in line.query("character") for span in target.singing]
        first = min((s.start for s in spans), default=line.lifetime.start)
        last = max((s.end for s in spans), default=line.lifetime.end)
        delay = line.query("line")[0].delay
        first, last = first + delay, last + delay
        entry_window = _transition_window(self.entry, self.entry_duration, entering=True)
        # Studio disables entry without preroll. With even a short preroll its
        # staggered characters keep their full attack during the first note.
        entry_total = min(first, entry_window)
        if first > 0 and self.entry in _CHAR_TRANSITIONS:
            entry_total = min(last, entry_window) if self.exit != "none" and self.exit_duration else entry_window
        release = 0.30 if self.singing.startswith("zoom_pulse") else 0
        exit_total = _transition_window(self.exit, self.exit_duration, entering=False)
        line = line.with_display(
            Lifetime(
                min(line.lifetime.start, max(0, first - entry_total)),
                max(line.lifetime.end, last + release + exit_total),
            )
        )
        original = {node.id: node for node in _walk(line)}
        if any(
            node.clip is not None or node.material is not None
            for target in line.query("character", "ruby")
            for node in (original[target.node_id],)
        ):
            raise ValueError(
                "KaraokeEffects must precede other highlight/material factories"
            )
        highlighter = LyricHighlights.from_singing(
            StatePatch(fill=self.sung, outline=self.sung_outline),
            wipe=self.singing != "no_wipe",
            reverse=self.reverse_wipe,
            ruby_reading_units=self.ruby_reading_units,
            base_paint=StatePatch(fill=self.unsung, outline=self.unsung_outline),
            material=self.material,
            base_material=self.base_material,
            glow=self.glow,
            base_glow=self.base_glow,
            secondary_outline=self.secondary_outline, sung_secondary_outline=self.sung_secondary_outline,
            hook_feather=self.hook_feather,
            front_color=self.front_color,
        )
        widths = highlighter._widths(line)
        line = highlighter._bind(line, widths)
        pulses_by_target: dict[str, tuple[_SingingPulse, ...]] = {}
        if self.singing.startswith(("utopia", "zoom_pulse")):
            arrival = HighlightArrival(highlights=highlighter.highlights)
            for target, _, index, _ in line._glyph_regions(automatic=True):
                unit = line.layout.lyrics.units[index]
                if target.role == "character" and any(s.ruby for s in unit.segments):
                    intervals = arrival(line, target)
                else:
                    intervals = tuple(TimeSpan(s.start + target.delay, s.end + target.delay)
                                      for s in target._visual_singing() if s.end > s.start)
                pulses_by_target[target.node_id] = _singing_pulses(
                    intervals, target, zoom=self.singing.startswith("zoom_pulse"), level=self.zoom_pulse_curve_level,
                )
        # The character-transition painter keeps the ordinary wipe and resumes
        # the luminous band on the frame after its inclusive entry window.
        singing_resume = line.lifetime.start + entry_total + 0.01 if first < entry_total else None
        line = replace(
            self, entry_duration=entry_total, exit_duration=exit_total
        )._ornaments(line, original, pulses_by_target, singing_resume, widths)
        reading_edges = _reading_edges(line)
        for entering, kind, total in (
            (True, self.entry, entry_total),
            (False, self.exit, exit_total),
        ):
            if kind == "none" or total == 0:
                continue
            # A line at the start of the song can begin singing during its
            # entrance. Reserve that actual span without asking for negative preroll.
            anchor = "enter" if entering else "exit"
            if entering and first < total:
                anchor = _display_start
            individual = (self.entry_unit if entering else self.exit_unit) == "character"
            if not individual and not entering and kind == "utopia":
                departures = line._resolve((LyricRule(
                    line.query("character", "ruby"), _utopia_exit_anchor(line, total, release),
                    partial(transition, kind=kind, entering=False, seed=self.seed,
                            zoom_pivot=self.singing.startswith("zoom_pulse")),
                    duration=total,
                ),))
                line = replace(line, _scheduled=(*line._scheduled, *(replace(b, catalog_exit=True) for b in departures)))
                continue
            animate = partial(transition, kind=kind, entering=entering, seed=self.seed,
                              zoom_pivot=self.singing.startswith("zoom_pulse"))
            if not individual and kind in {"fade", "slide_in", "slide_out", "rise"}:
                line = line.schedule(LyricRule("line", anchor, animate, duration=total))
                continue
            spread = total * (2 / 7 if kind in {"utopia", "tilt_pop"} else self.stagger)
            hosts = _character_hosts(line)
            # Legacy exits finish at the display end. Geometric exits and their
            # particles start at the beginning of the exit window.
            count_back = not entering and kind in _CHAR_TRANSITIONS
            offsets = (_character_offsets(line, hosts, spread, entering=not count_back, individual=individual)
                       if individual or kind not in {"glow_in", "glow_out"} else {})
            host_motion = kind in {"tracking_in", "wave_in", "scatter_out", "converge_out"}
            rules = []
            for target in line.query("character", "ruby"):
                delay = offsets.get(target.node_id, 0.0)
                if not entering and not count_back:
                    delay -= spread
                if entering and delay > 0:
                    rules.append(LyricRule(target, anchor, Transform(opacity=0),
                                           duration=delay, hold=False))
                motion = partial(animate, host=hosts[target.node_id] if host_motion and not individual else None,
                                 reading_edges=None if individual else reading_edges.get(target.node_id),
                                 glyph_pivot=individual)
                rules.append(LyricRule(target, anchor, motion, duration=total - spread, offset=delay))
            line = line.schedule(*rules)
        if pulses_by_target:
            rules = []
            for target in line.query("character", "ruby"):
                for pulse in pulses_by_target[target.node_id]:
                    rule = pulse.rule(target, singing_resume)
                    if rule is not None:
                        rules.append(rule)
            pulses = line._resolve(tuple(rules))
            line = replace(line, _scheduled=(*line._scheduled, *(replace(b, singing_release=True) for b in pulses)))
        return line

    def _scanline(
        self, layer: _ScanlineLayer, index: int, path: _BandPath,
        band: float, softness: float, top: float, bottom: float,
    ) -> Iterator[TextObject]:
        node, sides = layer.drawing, layer.sides
        material, before_material = layer.sung_brush, layer.waiting_brush
        if self.scanline_mode == "brighten" and self.scanline_brightness == 0:
            return
        assert self.scanline_color is not None and self.sung is not None and self.unsung is not None
        before = after = (self.scanline_color, self.scanline_color, material)
        if self.scanline_mode not in {"role", "color"}:

            def lifted(
                fill: Color, outline: Color, field: PaintField | None
            ) -> tuple[Color, Color, PaintField | None]:
                return (
                    _brighten(fill, self.scanline_brightness),
                    _brighten(outline, self.scanline_brightness),
                    field,
                )

            if sides:
                sung, waiting = sides
                before = lifted(
                    waiting.state.fill, waiting.state.outline, before_material
                )
                after = lifted(sung.state.fill, sung.state.outline, material)
            else:
                before = lifted(
                    self.unsung,
                    self.unsung_outline or node.state.outline,
                    before_material,
                )
                after = lifted(
                    self.sung, self.sung_outline or node.state.outline, material
                )
            if self.scanline_mode == "follow_before":
                after = before
            elif self.scanline_mode == "follow_after":
                before = after

        same_coverage = sides is None or (
            sides[0].state.border == sides[1].state.border
            and sides[0].state.opacity == sides[1].state.opacity
        )

        left_paint, right_paint = (before, after) if self.reverse_wipe else (after, before)
        def painted_slices() -> Iterator[
            tuple[float, float, float, tuple[Color, Color, PaintField | None]]
        ]:
            for lo, hi, strength in _scanline_slices(band, softness):
                if lo >= 0 or (after == before and (sides is None or strength == 1 and same_coverage)):
                    yield lo, hi, strength, right_paint
                elif hi <= 0:
                    yield lo, hi, strength, left_paint
                else:
                    yield lo, 0, strength, left_paint
                    yield 0, hi, strength, right_paint

        clip_type = _ColorStripClip if softness else RectangleClip
        for strip, (lo, hi, strength, paint) in enumerate(painted_slices()):
            empty = (0.0, top, 0.0, bottom)
            mask = RectangleKeyframes((
                (path[0][0], empty),
                *((t, (x + lo * per_px, top, x + hi * per_px, bottom)) for t, x, per_px in path),
                (path[-1][0], empty),
            ))
            field = paint[2]
            if sides:
                base = sides[0] if (hi <= 0) != self.reverse_wipe else sides[1]
                field = _mix_brush(base, paint[0], paint[1], field, strength)
                state = StatePatch(fill=paint[0], outline=paint[1]).interpolate(
                    base.state, strength
                )
            else:
                state = replace(
                    node.state,
                    fill=paint[0],
                    outline=paint[1],
                    blur=0,
                    shadow=Vec2(),
                    opacity=node.state.opacity * strength,
                )
            copy = replace(
                node,
                id=f"{node.id}/{self.id}:front:{index}:{strip}",
                lifetime=node.lifetime,
                clock_start=node.time_origin,
                animations=node.animations if sides else (),
                material=field,
                reference=None,
                layer=node.layer if sides else node.layer + 2,
                state=state,
                clip=clip_type(0, 0, 1, 1, space="local", deform=mask),
            )
            yield copy

    def _burst_plans(
        self, line: LyricLine, nodes: dict[str, SceneObject]
    ) -> Iterator[_Burst]:
        if self.decoration == "none" and self.entry not in _TRANSITION_COUNTS and self.exit not in _TRANSITION_COUNTS:
            return
        targets = line.query("character")
        sung_end = max(
            (span.end + target.delay for target in targets for span in target.singing),
            default=line.lifetime.start,
        )
        for index, target in enumerate(targets):
            node = nodes[target.node_id]
            if not isinstance(node, TextObject):
                continue
            for entering, kind, total in (
                (True, self.entry, self.entry_duration),
                (False, self.exit, self.exit_duration),
            ):
                count = _TRANSITION_COUNTS.get(kind)
                if (
                    total <= 0
                    or count is None
                    or (kind == "sparkle" and index != 0)
                ):
                    continue
                birth, duration = _transition_burst(
                    kind,
                    total,
                    entering,
                    line.lifetime,
                    sung_end,
                    self.stagger,
                    index,
                    len(targets),
                )
                yield _Burst(
                    target,
                    index,
                    node,
                    kind,
                    birth,
                    duration,
                    count,
                    "entry" if entering else "exit",
                )
            if not node.text.strip():
                continue
            for segment in target.singing:
                length = segment.end - segment.start
                if length <= 0 or self.decoration == "none":
                    continue
                duration, count = _SING_BURSTS[self.decoration]
                if self.particle_rate is not None and self.decoration != "ripple":
                    count = max(1, ceil(length * self.particle_rate))
                yield _Burst(
                    target,
                    index,
                    node,
                    self.decoration,
                    segment.start + target.delay,
                    duration,
                    count,
                    "singing",
                )

    def _follow_particle_ink(
        self, line: LyricLine,
    ) -> tuple[dict[str, tuple[_ParticlePaint, ...]], _ParticleTint | None]:
        """Resolve solid character palettes and the line sparkle's position-dependent color."""
        followed: dict[str, tuple[_ParticlePaint, ...]] = {}
        role_tint = None
        if not isinstance(self.particle_color, str) or self.particle_color == "illustrated":
            return followed, role_tint
        assert self.sung is not None and self.unsung is not None
        painted = {n.id: n for n in _walk(line)}
        centers: list[tuple[float, Color]] = []
        for target, glyph, unit, _ in line._glyph_regions(automatic=False):
            if target.role != "character":
                continue
            inks: list[_ParticlePaint] = []
            for mode, source, identity, fallback in (
                ("follow_before", self.base_material, target.node_id, self.unsung),
                ("follow_after", self.material, f"{target.node_id}/highlight:singing:{unit}", self.sung),
            ):
                if self.particle_color not in (mode, "follow_mix"):
                    continue
                piece = painted.get(identity)
                ink = _particle_ink(source, target, piece, fallback)
                if self.particle_layers == "solid" or piece is None:
                    inks.append(ink)
                    continue
                em = target.em_size or max(1, target.center.y * 2)
                strokes = self.particle_layers in ("stroke", "all")
                decor = self.particle_layers in ("decor", "all")
                border = min(0.25, piece.state.border / em) if strokes else 0
                halo = painted.get(identity + "/glow")
                rim = None
                outer = _hard_rim(painted.get(identity + "/secondary-outline") or halo, piece.state.border)
                if strokes and outer:
                    extra = min(0.25, (outer.state.border - piece.state.border) / em)
                    rim = Glow(outer.state.outline, border=border + extra, opacity=outer.state.opacity)
                soft = None
                offset = Vec2()
                if decor:
                    if halo and halo.state.blur:
                        if self.particle_glow_concentration >= 0 and halo.state.opacity:
                            soft = Glow(halo.state.outline, blur=halo.state.blur / em, opacity=halo.state.opacity)
                    else:
                        offset = piece.state.shadow * self.particle_size
                inks.append(replace(ink, outline=piece.state.outline, border=border, glow=rim,
                                    halo=soft, shadow_offset=offset, concentration=self.particle_glow_concentration))
            followed[target.node_id] = tuple(inks)
            centers.append((glyph.bounds.center, inks[0].fill))
        if self.particle_color != "follow_mix" and len({ink for _, ink in centers}) > 1:
            role_tint = _ParticleTint.from_roles(tuple(centers))
        return followed, role_tint

    def _particles(
        self,
        line: LyricLine,
        nodes: dict[str, SceneObject],
        additions: dict[str, list[SceneObject]],
        *,
        transitions: bool,
    ) -> LyricLine:
        plans = tuple(self._burst_plans(line, nodes))
        if sum(plan.count for plan in plans) > self.max_particles:
            raise ValueError("karaoke particle budget exceeded before construction")
        active = [(i, p) for i, p in enumerate(plans) if (p.phase != "singing") == transitions]
        if not active:
            return line
        followed, role_tint = self._follow_particle_ink(line)
        line_particles: list[SceneObject] = []
        for plan_index, plan in active:
            target, node, kind = plan.target, plan.node, plan.kind
            entering, exiting = plan.phase == "entry", plan.phase == "exit"
            em = target.em_size or max(1, target.center.y * 2)
            seed = self.seed + (line.track_index & 0xFFFF) * 0x9E37
            display = line.lifetime if entering or exiting else None
            palette = self.particle_color
            pens: tuple[_ParticlePaint, ...] = ()
            if palette == "illustrated":
                if display is None:
                    colors = (Color(255, 255, 255),)
                elif kind.startswith("snow"):
                    colors = (Color(242, 248, 255), Color(191, 223, 255))
                else:
                    colors = (Color(255, 183, 197), Color(255, 215, 224))
            elif isinstance(palette, str):
                paints = followed[target.node_id]
                colors = tuple(paint.fill for paint in paints)
                if (self.particle_layers != "solid" and kind != "ripple"
                        and (kind != "sparkle" or palette == "follow_mix")):
                    pens = paints
            elif isinstance(palette, tuple):
                colors = (palette[0],) if palette[0] == palette[1] else palette
            else:
                assert isinstance(palette, Color)
                colors = (palette,)
            if kind == "sparkle":
                bounds = line.layout.body.bounds
                center, box = (
                    Vec2(bounds.center, bounds.middle),
                    Vec2(bounds.width, bounds.height),
                )
                seed += 1 if entering else 3
                destination = line_particles
            else:
                # The pen origin can sit inside the lyric cell. Particle spread
                # uses the entire measured cell, independent of that offset.
                cell = line.layout.body.characters[plan.glyph_index].bounds
                center = node.state.transform.apply(target.center)
                box = Vec2(cell.width, cell.height)
                seed += plan.glyph_index + _burst_seed(kind, entering, exiting)
                destination = additions.setdefault(node.id, [])
            context = ParticleContext(
                f"{node.id}/{self.id}:particle:{plan_index}",
                plan.start,
                seed,
                center,
                line.origin,
            )
            fields: tuple[_ParticleTint | None, ...] = ()
            if kind == "sparkle" and palette in ("follow_before", "follow_after"):
                fields = (role_tint,)
            elif palette in ("follow_before", "follow_after", "follow_mix") and self.particle_layers != "solid":
                bounds = line.layout.body.bounds
                # Character ornaments move in their parent's local coordinates;
                # sparkle already uses the whole line's coordinate system.
                left = bounds.left
                if kind != "sparkle":
                    left += center.x - line.layout.body.characters[plan.glyph_index].bounds.center
                fields = tuple(
                    paint.across_line(left, bounds.width, stroke=bool(pens))
                    for paint in followed[target.node_id]
                )
            if kind in {"sparkle", "twinkle", "twinkle_classic"}:
                destination.extend(
                    star_burst(
                        context,
                        kind,
                        box=box,
                        size=em * self.particle_size,
                        duration=plan.duration,
                        count=plan.count,
                        colors=colors, pens=pens,
                        fields=fields,
                        exiting=exiting,
                        display=display,
                    )
                )
                continue
            # Studio draws the entire first colour burst before the second.
            for stream, color in enumerate(colors):
                radial = None
                if kind == "ripple" and self.particle_layers != "solid" and isinstance(palette, str):
                    gradient = followed[target.node_id][stream].gradient
                    if gradient is not None and gradient.axis == "y":
                        radial = gradient.fill
                for sample, index in enumerate(range(stream, plan.count, len(colors))):
                    particle = ornament(
                        replace(
                            context,
                            id=f"{context.id}:{index}",
                            seed=seed + sample + stream * 0x9E37,
                        ),
                        kind,
                        box=box,
                        em=em,
                        size=em * self.particle_size,
                        index=sample,
                        radial=radial,
                        duration=plan.duration,
                        color=color,
                        entering=entering,
                        exiting=exiting,
                        display=display,
                    )
                    if particle is not None:
                        destination.extend(painted_particle(
                            particle, pens[stream] if pens else None, fields[stream] if fields else None,
                        ))
        return replace(line, children=(*line.children, *line_particles))

    def _display_ornaments(self, line: LyricLine) -> LyricLine:
        """Place transition decorations on the same allocated clock as their text."""
        nodes = {node.id: node for node in _walk(line)}
        additions: dict[str, list[SceneObject]] = {}
        line = self._particles(line, nodes, additions, transitions=True)
        replacements: dict[str, TextObject] = {}
        fade_offsets = (_character_offsets(line, _character_hosts(line), self.exit_duration * self.stagger, entering=False, individual=self.exit_unit == "character")
                        if self.exit in {"char_fade", "spin_flip"} else {})
        # Horizontal glow echoes have their own envelope, beneath the sharp glyph.
        for target in line.query("character", "ruby"):
            node = nodes[target.node_id]
            if not isinstance(node, TextObject) or not node.text.strip():
                continue
            for entering, kind, total in (
                (True, self.entry, self.entry_duration),
                (False, self.exit, self.exit_duration),
            ):
                if total <= 0:
                    continue
                if kind in {"stretch_in", "stretch_out", "char_drip", "spin_flip"}:
                    for alias in (target.node_id, *target.aliases):
                        ink = nodes[alias]
                        if isinstance(ink, TextObject):
                            replacements[alias] = replace(ink, scale_border=True)
                if not entering and kind in {"char_fade", "spin_flip"}:
                    start = line.lifetime.end - total * (1 - self.stagger) + fade_offsets[target.node_id]
                    for ink in (node, nodes.get(node.id + "/secondary-outline"), nodes.get(node.id + "/glow")):
                        if isinstance(ink, TextObject):
                            replacements[ink.id] = _fade_underpaint(replacements.get(ink.id, ink), start)
                    continue
                if kind in {"stretch_in", "stretch_out"}:
                    if target.role == "ruby":
                        continue
                    peers = line.query(target.role)
                    index = peers.index(target)
                    start = (
                        line.lifetime.start if entering else line.lifetime.end - total
                    )
                    birth = start + total * self.stagger * index / max(
                        1, len(peers) - 1
                    )
                    additions.setdefault(node.id, []).extend(
                        _stretch_halo(
                            node,
                            target.em_size or node.font_size,
                            target.center,
                            f"{node.id}/{self.id}:halo:{kind}",
                            entering,
                            birth,
                            total * (1 - self.stagger),
                            self.shine or node.state.fill,
                        )
                    )
                    continue
                if target.role == "ruby" or kind not in {"glow_in", "glow_out"}:
                    continue
                birth = line.lifetime.start if entering else line.lifetime.end - total
                travel_duration = total * (1 - self.stagger)
                for echo_index in (*range(-14, 0), *range(1, 15)):
                    distance = (target.em_size or node.font_size) * 0.12 * echo_index

                    def envelope(p: float, enter: bool = entering) -> float:
                        q = smooth_rate(p)
                        return (1 - q) * sqrt(max(0, 1 - q)) if enter else sin(pi * q)

                    def travel(
                        p: float, enter: bool = entering, x: float = distance
                    ) -> Vec2:
                        q = smooth_rate(p)
                        pitch = 1 - 0.25 * q if enter else 1 + 0.9 * q
                        return Vec2(x * pitch * glow_scale(q, enter).x, 0)

                    def scale(p: float, enter: bool = entering) -> Vec2:
                        return glow_scale(smooth_rate(p), enter)

                    echo = replace(
                        node,
                        id=f"{node.id}/{self.id}:echo:{kind}:{echo_index}",
                        lifetime=Lifetime(birth, birth + travel_duration),
                        clock_start=birth,
                        animations=(),
                        clip=None,
                        material=None,
                        reference=None,
                        layer=node.layer - 1,
                        state=replace(
                            node.state,
                            fill=self.shine or node.state.fill,
                            blur=0,
                            border=0,
                            shadow=Vec2(),
                            opacity=0.82 ** abs(echo_index),
                        ),
                    )
                    motion = Transform(offset=travel, opacity=envelope, scale=scale, pivot=target.center)
                    echo = echo.animate(
                        ShaderMotion(motion.sample, motion.channels, """
                            bool enter=item(data+2)>0.;
                            float q=smoothstep(0.,1.,p), sx=1.+0.6*(enter?1.-q:q);
                            mat2 before=basisOf(scale,skew,angle);
                            scale.x*=sx;
                            pos+=(before-basisOf(scale,skew,angle))*pairAt(data);
                            pos.x+=item(data+3)*(enter?1.-0.25*q:1.+0.9*q)*sx;
                            alpha*=enter?(1.-q)*sqrt(max(0.,1.-q)):sin(3.14159265*q);
                        """,(target.center.x,target.center.y,float(entering),distance)),
                        duration=travel_duration,
                    )
                    additions.setdefault(node.id, []).append(echo)
        return _insert(line, additions, reserve=False, replacements=replacements)

    def _ornaments(self, line: LyricLine, nodes: dict[str, SceneObject],
                   pulses_by_target: dict[str, tuple[_SingingPulse, ...]], band_start: float | None,
                   widths: dict[float, float]) -> LyricLine:
        additions: dict[str, list[SceneObject]] = {}
        line = self._particles(line, nodes, additions, transitions=False)
        transition_kinds = {
            "char_drip", "spin_flip",
            "glow_in",
            "glow_out",
            "stretch_in",
            "stretch_out",
            *_TRANSITION_COUNTS,
        }
        if self.entry in transition_kinds or self.exit in transition_kinds | {"char_fade"}:
            if line._at_placement is None:
                line = self._display_ornaments(line)
            else:
                def decorate(placed: LyricLine, entry_scale: float, exit_scale: float) -> LyricLine:
                    return replace(
                        self, entry_duration=self.entry_duration * entry_scale,
                        exit_duration=self.exit_duration * exit_scale,
                    )._display_ornaments(placed)
                line = replace(line, _at_placement=(*line._at_placement, decorate))
        if "scanline" not in self.singing and not self.stroke_flash:
            return _insert(line, additions)
        # The front follows glyph motion. Studio flashes the original measured outline.
        aliases: dict[str, list[str]] = {}
        painted_nodes = {n.id: n for n in _walk(line)} if "scanline" in self.singing else {}
        replacements: dict[str, TextObject] = {}
        glyphs = tuple(line._glyph_regions(automatic=True))
        # At unit boundaries the moving band can still intersect ink on either side.
        # Use the nearest edge glyph's measured sweep when tracking across added spacing.
        # Body notes share one front. Each annotated unit has its own reading front.
        reading_slots = {
            target.node_id: (unit, slot)
            for slot, (target, _, unit, _) in enumerate(glyphs)
            if target.role == "ruby"
        }
        reading_only = {
            i for i, u in enumerate(line.layout.lyrics.units)
            if self.ruby_scanline == "reading" and u.segments
            and all(s.ruby is not None for s in u.segments)
            and any(s.ruby and s.ruby.source.text.strip() for s in u.segments)
        }
        edges: dict[int | None, dict[int, tuple[tuple[_Sweep, ...], tuple[_Sweep, ...]]]] = {}
        sweeps: dict[str, tuple[_Sweep, ...]] = {}
        transformed_band = self.singing in {"utopia_scanline", "zoom_pulse_scanline"}
        if "scanline" in self.singing:
            intervals: dict[int | None, set[tuple[float, float]]] = {}
            reading_ends: dict[int, float] = {}
            for target, _, unit, _ in glyphs:
                group, _slot = reading_slots.get(target.node_id, (None, unit))
                spans = target._visual_singing()
                intervals.setdefault(group, set()).update(
                    (s.start + target.delay, s.end + target.delay) for s in spans if s.end > s.start
                )
                if group is not None:
                    reading_ends[group] = line.layout.lyrics.units[unit].segments[-1].singing.end + target.delay
            clocks = {g: _front_clock(notes, reading_ends.get(g) if g is not None else None)
                      for g, notes in intervals.items()}
            body_clocks = {
                i: line.layout._body_wipe(unit, reading_units=self.ruby_reading_units, reverse=self.reverse_wipe)
                for i, unit in enumerate(line.layout.lyrics.units)
            }
            # A zero-duration space separates words on the page but contributes
            # no sung endpoint. Keep the last timed word for the handoff frame.
            previous_body_slots: list[int] = []
            previous_slot = -1
            for slot, lyric in enumerate(line.layout.lyrics.units):
                previous_body_slots.append(previous_slot)
                text = line.layout.body.source.text[lyric.start:lyric.end]
                if text.strip() or any(s.end > s.start for s, _, _ in body_clocks[slot]):
                    previous_slot = slot
            for target, glyph, unit, box in glyphs:
                group, slot = reading_slots.get(target.node_id, (None, unit))
                track = edges.setdefault(group, {})
                body = group is None
                previous = track.get(previous_body_slots[slot]) if body and not self.reverse_wipe else None
                clock = body_clocks[unit] if body else ((target._reading_span or target.singing[0], 0, 1),)
                first_note, releases = clocks[group]
                if not body and transformed_band:
                    # The animated painter sweeps each reading fragment across its font
                    # advance and draws its strip strictly inside that fragment's note.
                    advance = glyph._font_advance
                    box = replace(box, left=glyph.object.state.position.x,
                                  width=glyph.bounds.width if advance is None else advance)
                    first_note, releases = clock[0][0].start + target.delay, {}
                passes = _sweeps(clock, target.delay, box,
                                 previous[1] if previous else (),
                                 first_note, releases,
                                 first_pixel=0.5 if body else 0.0, reverse=self.reverse_wipe)
                sweeps[target.node_id] = () if body and unit in reading_only else passes
                first, _ = track.get(slot, (passes, passes))
                track[slot] = first, passes
        ratio = line.layout.script_height / 1080
        band_width = max(1, round(16 * ratio)) if self.scanline_width is None else self.scanline_width
        band_softness = round(8 * ratio) if self.scanline_softness is None else self.scanline_softness
        reading_hosts = _character_hosts(line) if reading_slots and "scanline" in self.singing else {}
        run_spans = _scanline_run_spans(line) if "scanline" in self.singing else {}
        for target, glyph, unit, _ in glyphs:
            node = nodes[target.node_id]
            if not isinstance(node, TextObject) or not node.text.strip():
                continue
            material: PaintField | None = None
            span = run_spans.get(glyph.object.id)
            if span is not None and self.singing == "zoom_pulse_scanline":
                span = _line_x(glyph, glyph.bounds.left, glyph.bounds.right)
            before_material = None
            if self.scanline_mode == "role":
                source = _style_material(self.scanline_material, target.source_style)
                material = _scanline_brush(source, target, span, None)
                if material is None:
                    material = _resolve_material(source, line, target)
                if isinstance(material, LinearGradient) and material.fill is not None:
                    material = replace(material, outline=material.fill)
            elif self.scanline_mode in {"brighten", "follow_before", "follow_after"} and painted_nodes:
                if self.scanline_mode != "follow_after":
                    field = _scanline_brush(self.base_material, target, span, painted_nodes[target.node_id].material)
                    if isinstance(field, LinearGradient):
                        before_material = _brighten_gradient(field, self.scanline_brightness)
                if self.scanline_mode != "follow_before":
                    sung = next((painted_nodes[a].material for a in target.aliases
                                 if isinstance(painted_nodes[a].material, LinearGradient)), None)
                    field = _scanline_brush(self.material, target, span, sung)
                    if isinstance(field, LinearGradient):
                        material = _brighten_gradient(field, self.scanline_brightness)
            if "scanline" in self.singing:
                width = _width(band_width, node.font_size, line.layout.script_height, f"{node.id}: scanline_width")
                softness = _width(band_softness, node.font_size, line.layout.script_height, f"{node.id}: scanline_softness")
                if width == 0:
                    raise ValueError(f"{node.id}: scanline_width must be positive")
                assert glyph.layout_scale is not None
                scale = glyph.layout_scale
                ink = glyph.ink_bounds or glyph.bounds
                base = painted_nodes[target.node_id]
                sung_id = f"{node.id}/highlight:singing:{unit}"
                sung_piece = painted_nodes.get(sung_id)
                rims = _hard_rims(painted_nodes, node, sung_id)
                # The repaint uses the host pen. A soft adjustment only changes
                # pixels covered by both that pen and the original reading.
                band_node = node
                inside_reading = False
                if target.role == "ruby":
                    host = nodes[reading_hosts[target.node_id].node_id]
                    border = host.state.border
                    if self.scanline_mode in {"color", "role"}:
                        host_rims = _hard_rims(painted_nodes, host, f"{host.id}/highlight:singing:{unit}")
                        after, before = (rim.state.border if rim else border for rim in host_rims)
                        if before == after:
                            # Qt tests nonzero antialiased coverage. Allow half a
                            # pixel of fringe, leaving a full pixel of opaque ink.
                            reading_border = min(
                                rim.state.border if rim and rim.state.opacity == 1 else node.state.border
                                for rim in rims
                            )
                            inside_reading = (
                                softness > 0 and node.state.opacity == 1 and before + 1.5 <= reading_border
                            )
                            if softness == 0 or inside_reading:
                                border = before + (0.5 if inside_reading else 0)
                                rims = (None, None)
                    if softness == 0 or inside_reading:
                        band_node = replace(node, state=replace(node.state, border=border))
                pad = max((band_node.state.border, *(r.state.border for r in rims if r))) + 2
                # During a pulse Studio repaints only the height of the transformed fill.
                vertical_pad = 0 if transformed_band else pad
                top = (ink.top - glyph.bounds.top) / scale.y - vertical_pad
                bottom = (ink.top + ink.height - glyph.bounds.top) / scale.y + vertical_pad
                movements = list(sweeps[target.node_id])
                group, slot = reading_slots.get(target.node_id, (None, unit))
                reach = width / 2 + pad * scale.x
                neighbors = edges[group].items() if group is None or not transformed_band else ()
                for other, (first, last) in neighbors:
                    if other == slot or (group is None and other in reading_only):
                        continue
                    for sweep in last if other < slot else first:
                        overlap = sweep.intersect(ink.left - reach, ink.right + reach)
                        if overlap is not None:
                            movements.append(overlap)
                if band_start is not None:
                    movements = [s.after(band_start) for s in movements if s.end > band_start]
                paths = tuple(
                    tuple(
                        (
                            local_seconds(t, node.time_origin),
                            (x - glyph.object.state.position.x) / scale.x,
                        )
                        for t, x in path
                    )
                    for path in _front_paths(movements)
                )
                layers: list[_ScanlineLayer] = []
                native_pass = (
                    not widths[glyph.object.font_size]
                    and all(a[-1][0] < b[0][0] for a, b in pairwise(paths))
                    and not (
                        self.scanline_mode == "brighten"
                        and self.scanline_brightness == 0
                    )
                )
                sides = None
                if (
                    native_pass
                    and isinstance(base, TextObject)
                    and isinstance(sung_piece, TextObject)
                    and all(
                        isinstance(p.clip, RectangleClip)
                        and isinstance(p.clip.deform, RectangleKeyframes)
                        for p in (base, sung_piece)
                    )
                ):
                    if (
                        softness > 0 and not inside_reading
                        and _compatible_brushes(base.material, sung_piece.material, material, before_material)
                    ):
                        sides = sung_piece, base
                    sung_rim, waiting_rim = rims
                    if sung_rim and waiting_rim:
                        brush = material if self.scanline_mode == "role" else None
                        if _compatible_brushes(brush):
                            layers.append(
                                _ScanlineLayer(sung_rim, brush, None, (sung_rim, waiting_rim))
                            )
                layers.append(_ScanlineLayer(band_node, material, before_material, sides))
                pulses = pulses_by_target.get(target.node_id, ())
                band_paths = tuple(_band_path(p, scale.x, node.time_origin, pulses, width) for p in paths)
                for layer in layers:
                    strip_top, strip_bottom = top, bottom
                    if band_paths and layer.sides and (not transformed_band or softness > 0):
                        if not transformed_band:
                            strip_top, strip_bottom = -65536, 65536
                        sung, waiting = layer.sides
                        left_piece, right_piece = (waiting, sung) if self.reverse_wipe else (sung, waiting)
                        for piece, offset, left in (
                            (left_piece, -width / 2, True),
                            (right_piece, width / 2, False),
                        ):
                            outside = _outside_front(piece, band_paths, offset, left=left)
                            if transformed_band:
                                # Studio only adjusts the transformed ink's height. Preserve the
                                # unadjusted stroke above and below it using the same source wipe.
                                for name, a, b in (("above", -65536, top), ("below", bottom, 65536)):
                                    cap = _clip_rows(piece.copy(id=f"{piece.id}/scanline:{name}"), a, b)
                                    additions.setdefault(piece.id, []).append(cap)
                                    aliases.setdefault(target.id, []).append(cap.id)
                                outside = _clip_rows(outside, top, bottom)
                            replacements[piece.id] = outside
                    for index, band_path in enumerate(band_paths):
                        for front in self._scanline(
                            layer, index, band_path, width, softness, strip_top, strip_bottom
                        ):
                            additions.setdefault(layer.drawing.id, []).append(front)
                            aliases.setdefault(target.id, []).append(front.id)
            if not self.stroke_flash or target.role != "character":
                continue
            outline = outline_text(node)
            if outline.path is None:
                continue
            pen = max(2 * node.state.border, (target.em_size or node.font_size) * 0.03)
            path = outline.path
            paint = contour_stroke(path, 0.8 * pen)

            for index, span in enumerate(line.layout.lyrics.units[unit]._body_singing()):
                onset = span.start + target.delay
                end = min(node.lifetime.end, onset + 0.24)
                if end <= onset:
                    continue
                duration = end - onset

                def flash(base: VisualState, p: float, width: float = pen, window: float = duration) -> VisualState:
                    level = max(0, 1 - p * window / 0.24)
                    return replace(base, opacity=0.85 * level, border=width * (0.5 + 0.3 * level))

                copy = PathObject(
                    id=f"{node.id}/{self.id}:flash:{index}",
                    shader_paint=paint,
                    filled=False,
                    lifetime=Lifetime(onset, end),
                    origin=node.origin,
                    # Draw after this glyph's hard scanline and before foreground ornaments.
                    layer=node.layer + 2,
                    state=replace(node.state, opacity=0, fill=self.shine or node.state.fill,
                                  outline=self.shine or node.state.outline, border=0, blur=0, shadow=Vec2()),
                    path=path,
                ).animate(
                    ShaderMotion(flash, frozenset({"opacity", "border"}), """
                        float level=max(0.,1.-p*item(data+1)/0.24);
                        alpha=0.85*level; pen=item(data)*(0.5+0.3*level);
                    """,(pen,duration)),
                    duration=duration,
                )
                additions.setdefault(node.id, []).append(copy)
        result = _insert(line, additions, replacements=replacements)
        return replace(
            result,
            targets=tuple(
                replace(t, aliases=(*t.aliases, *aliases.get(t.id, ())))
                for t in result.targets
            ),
        )
