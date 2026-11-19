"""A complete, configurable karaoke animation recipe using ordinary Scene objects."""

from collections.abc import Callable, Iterator
from dataclasses import dataclass, replace
from functools import partial
from itertools import groupby, pairwise
from math import ceil, floor, pi, sin, sqrt
from typing import Literal, get_args

from ._karaoke_motion import glow_scale, stretch, transition, zoom_pulse
from ._karaoke_sprites import ornament, star_burst
from .composition import Color
from .document_text import SingingSpan
from .geometry import Vec2, VectorPath, finite
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
    LyricAnimationContext,
    LyricLine,
    LyricRule,
    LyricTarget,
    _KaraokePaint,
    _line_x,
)
from .model import Box
from .paint_fields import ColorRamp, ColorStop, LinearGradient, PaintField, _mix
from .particles import ParticleContext
from .path_geometry import flatten, stroke
from .scene import (
    Lifetime,
    ObjectGroup,
    PathObject,
    RectangleClip,
    RectangleKeyframes,
    SceneObject,
    TextObject,
)
from .scene_animation import (
    ScalePulse,
    StateFunction,
    StatePatch,
    TimeSpan,
    Transform,
    VisualState,
    linear_rate,
    local_seconds,
    smooth_rate,
)
from .text_geometry import outline_text

_DUOTONE_UNSUNG = Color(40, 28, 38)
_DUOTONE_UNSUNG_OUTLINE = Color(255, 247, 232)
_DUOTONE_SUNG = Color(255, 232, 169)
_DUOTONE_SUNG_OUTLINE = Color(173, 66, 26)

type KaraokeEntry = Literal[
    "none",
    "fade",
    "slide_in",
    "rise",
    "char_fade",
    "char_drip",
    "spin_flip",
    "utopia",
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
) -> Iterator[TextObject]:
    motion = stretch(entering, pivot)
    white = Color(255, 255, 255)
    for width, strength in (
        (0.10, 0.42),
        (0.22, 0.24),
        (0.38, 0.14),
        (0.58, 0.08),
        (0.82, 0.045),
    ):

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
                fill=white,
                outline=white,
                border=0,
                blur=0,
                shadow=Vec2(),
                opacity=node.state.opacity * strength,
            ),
        )
        yield copy.animate(
            StateFunction(
                sample, frozenset({"position", "scale", "opacity", "border"})
            ),
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
    scale = total / 0.60
    if kind == "sparkle":
        if entering:
            return display.start, 0.70 * scale
        start = min(display.end - 0.12, max(sung_end, display.end - total))
        return start, display.end - start
    if kind in {"snow", "snow_solid"}:
        if entering:
            return display.start - 0.20 * scale, total + 0.45 * scale
        start = max(sung_end, display.end - total)
        return start, display.end - start + 0.30 * scale
    spread = total * stagger
    duration = {
        "petal": 0.90,
        "note": 0.80,
        "ripple": 0.60,
        "assemble_in": 0.32,
        "dissolve_out": 0.32,
    }.get(kind)
    travel = duration * scale if duration is not None else total - spread
    start = display.start
    if not entering:
        start = min(display.end - 0.12, max(sung_end, display.end - spread - travel))
        spread = min(spread, max(0, display.end - start - travel))
    return start + spread * index / max(1, count - 1), travel


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
                       *, entering: bool) -> dict[str, float]:
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


def _transition_window(kind: str, configured: float, *, entering: bool) -> float:
    if kind == "none" or configured == 0:
        return 0
    if kind == "utopia":
        return 0.70 if entering else 0.75
    if kind in _CHAR_TRANSITIONS:
        return 0.60
    if kind in {"fade", "slide_in", "slide_out", "rise"}:
        return configured
    return min(3, max(0.12, configured))


def _utopia(context: LyricAnimationContext) -> ScalePulse:
    attack_ms = min(round(context.duration * 1000) // 4, 100)
    return ScalePulse(
        peak=1.15 if attack_ms else 1,
        peak_at=attack_ms / (1000 * context.duration) if attack_ms else 0.5,
        rate=linear_rate,
        pivot=Vec2(0, context.target.baseline)
        if context.target.baseline is not None
        else context.target.center,
    )


def _zoom(context: LyricAnimationContext, *, level: int) -> Transform:
    note = context.interval.duration if context.interval is not None else context.duration
    return zoom_pulse(max(note, 0.001), context.duration, level, context.target.center)


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


def _outside_front(
    piece: TextObject, paths: tuple[_FrontPath, ...], offset: float, *, left: bool
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
        for time, x in path:
            xmin, t, xmax, b = original.bounds_at(time)
            keys.append(
                (time, (xmin, t, x + offset, b) if left else (x + offset, t, xmax, b))
            )
        keys.append((end, original.bounds_at(end)))
    keys.sort(key=lambda key: key[0])
    return replace(piece, clip=replace(clip, deform=RectangleKeyframes(tuple(keys))))


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
    Ornament tails reserve display without altering source singing intervals.
    material/glow/base_glow use the same factories as LyricHighlights.
    Entry is shortened only when Scene zero leaves insufficient preview time.
    Exit starts after singing (including zoom release), reserving needed tail.
    Overlapping repeats truncate the preceding zoom release and restart its pulse.

    Includes the Studio animation-menu families, independently implemented on
    this engine. It is a visual recipe, not an importer or pixel-identical renderer.
    Use ordinary LyricRule/custom effects alongside it. Apply once per line, before
    another highlight factory; this recipe owns the base/sung appearance and masks.
    Decorations use seeded glyph-local trajectories; ruby receives text transitions
    and sweeps but not particles or outline flash. max_particles bounds the total
    generated ornament objects per line, including entry and exit.

    Standard ASS is supported (complex motion is sampled). GPU enhancement uses
    the same Scene; dynamic blur can require additional cached native coverage.
    No dependency on Manim, Qt, or the reference application is introduced.
    """

    entry: KaraokeEntry = "fade"
    exit: KaraokeExit = "fade"
    singing: KaraokeSinging = "utopia"
    reverse_wipe: bool = False
    decoration: KaraokeDecoration = "none"
    entry_duration: float = 0.3
    exit_duration: float = 0.3
    stagger: float = 7 / 12
    sung: Color = Color(255, 90, 111)
    unsung: Color = Color(255, 255, 255)
    material: LyricMaterial = None
    base_material: LyricMaterial = None
    glow: LyricGlow = None
    base_glow: LyricGlow = None
    particle_color: Color | None = None
    particle_size: float = 0.40
    particle_rate: float | None = None
    max_particles: int = 512
    seed: int = 0
    zoom_pulse_curve_level: int = 1
    scanline_width: float | None = None
    scanline_softness: float | None = None
    scanline_mode: Literal[
        "color", "brighten", "follow_before", "follow_after", "role"
    ] = "color"
    ruby_scanline: Literal["reading", "both"] = "reading"
    scanline_material: LyricMaterial = None
    scanline_brightness: float = 0.60
    scanline_color: Color = Color(255, 255, 255)
    hook_feather: float = 0
    front_color: Color | None = None
    unsung_outline: Color | None = None
    sung_outline: Color | None = None
    stroke_flash: bool = False
    id: str = "karaoke"

    @property
    def _hard_border(self) -> float:
        return max(_hard_glow_border(self.base_glow), _hard_glow_border(self.glow))

    @classmethod
    def duotone(
        cls,
        *,
        unsung: Color = _DUOTONE_UNSUNG,
        unsung_outline: Color = _DUOTONE_UNSUNG_OUTLINE,
        sung: Color = _DUOTONE_SUNG,
        sung_outline: Color = _DUOTONE_SUNG_OUTLINE,
        feather: float = 24,
    ) -> "KaraokeEffects":
        """Wipe between two fill/outline pairs. The moving boundary carries no separate ink."""
        return cls(
            singing="none",
            sung=sung,
            unsung=unsung,
            sung_outline=sung_outline,
            unsung_outline=unsung_outline,
            hook_feather=feather,
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
        width = 16 if self.scanline_width is None else self.scanline_width
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
        if self.scanline_softness is not None:
            finite(self.scanline_softness)
            if self.scanline_softness < 0:
                raise ValueError("scanline softness must be nonnegative")
        if not isinstance(self.scanline_color, Color):
            raise TypeError("scanline_color must be a Color")
        rate = 1 if self.particle_rate is None else self.particle_rate
        finite(
            self.entry_duration,
            self.exit_duration,
            self.stagger,
            self.particle_size,
            rate,
            width,
            self.hook_feather,
        )
        if (
            min(self.entry_duration, self.exit_duration) < 0
            or not 0 <= self.stagger < 1
        ):
            raise ValueError("durations must be nonnegative and stagger in [0,1)")
        if self.hook_feather < 0:
            raise ValueError("hook feather must be nonnegative")
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
            or not isinstance(self.sung, Color)
            or not isinstance(self.unsung, Color)
        ):
            raise ValueError("effects need an id and Color paints")
        if self.particle_color is not None and not isinstance(
            self.particle_color, Color
        ):
            raise TypeError("particle_color must be a Color or None")

    def __call__(self, line: LyricLine) -> LyricLine:
        """Prepare appearance and defer text motion through the common lyric rules."""
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
        entry_total = min(
            _transition_window(self.entry, self.entry_duration, entering=True), first
        )
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
            base_paint=StatePatch(fill=self.unsung, outline=self.unsung_outline),
            material=self.material,
            base_material=self.base_material,
            glow=self.glow,
            base_glow=self.base_glow,
            hook_feather=self.hook_feather,
            front_color=self.front_color,
        )
        line = highlighter(line)
        line = replace(
            self, entry_duration=entry_total, exit_duration=exit_total
        )._ornaments(line, original)
        reading_edges = _reading_edges(line)
        for entering, kind, total in (
            (True, self.entry, entry_total),
            (False, self.exit, exit_total),
        ):
            if kind == "none" or total == 0:
                continue
            anchor = "enter" if entering else "exit"
            if not entering and kind == "utopia":
                line = line.schedule(LyricRule(
                    line.query("character", "ruby"), _utopia_exit_anchor(line, total, release),
                    partial(transition, kind=kind, entering=False, seed=self.seed,
                            zoom_pivot=self.singing.startswith("zoom_pulse")),
                    duration=total,
                ))
                continue
            animate = partial(transition, kind=kind, entering=entering, seed=self.seed,
                              zoom_pivot=self.singing.startswith("zoom_pulse"))
            if kind in {"fade", "slide_in", "slide_out", "rise"}:
                line = line.schedule(LyricRule("line", anchor, animate, duration=total))
                continue
            spread = total * (2 / 7 if kind == "utopia" else self.stagger)
            hosts = _character_hosts(line)
            # Legacy exits finish at the display end. Geometric exits and their
            # particles start at the beginning of the exit window.
            count_back = not entering and kind in _CHAR_TRANSITIONS
            offsets = (_character_offsets(line, hosts, spread, entering=not count_back)
                       if kind not in {"glow_in", "glow_out"} else {})
            host_motion = kind in {"tracking_in", "wave_in", "scatter_out", "converge_out"}
            rules = []
            for target in line.query("character", "ruby"):
                delay = offsets.get(target.node_id, 0.0)
                if not entering and not count_back:
                    delay -= spread
                if entering and delay > 0:
                    rules.append(LyricRule(target, "enter", Transform(opacity=0),
                                           duration=delay, hold=False))
                motion = partial(animate, host=hosts[target.node_id] if host_motion else None,
                                 reading_edges=reading_edges.get(target.node_id))
                rules.append(LyricRule(target, anchor, motion, duration=total - spread, offset=delay))
            line = line.schedule(*rules)
        if self.singing.startswith(("utopia", "zoom_pulse")):
            rules = []
            arrival = HighlightArrival(highlights=highlighter.highlights)
            for target, _, index, _ in line._glyph_regions(automatic=True):
                unit = line.layout.lyrics.units[index]
                if target.role == "character" and any(s.ruby for s in unit.segments):
                    intervals = arrival(line, target)
                else:
                    intervals = tuple(TimeSpan(s.start + target.delay, s.end + target.delay)
                                      for s in target._visual_singing() if s.end > s.start)
                for i, interval in enumerate(intervals):
                    def anchor(
                        _line: LyricLine, _target: LyricTarget, span: TimeSpan = interval,
                    ) -> tuple[TimeSpan, ...]:
                        return (span,)

                    if self.singing.startswith("utopia"):
                        rules.append(LyricRule(target, anchor, _utopia))
                    else:
                        release = min(0.30, intervals[i + 1].start - interval.end
                                      ) if i + 1 < len(intervals) else 0.30
                        rules.append(LyricRule(
                            target, anchor, partial(_zoom, level=self.zoom_pulse_curve_level),
                            duration=interval.duration + max(0, release), hold=False,
                        ))
            line = line.schedule(*rules)
        return replace(
            line,
            _karaoke_paint=None
            if "scanline" in self.singing
            else _KaraokePaint(
                self.sung,
                self.unsung,
                entry_total,
                exit_total,
                self.singing != "no_wipe",
                self.unsung_outline,
                self.sung_outline,
                self.hook_feather,
                self.reverse_wipe,
            ),
        )

    def _scanline(
        self, layer: _ScanlineLayer, index: int, path: _FrontPath,
        band: float, softness: float, top: float, bottom: float,
    ) -> Iterator[TextObject]:
        node, sides = layer.drawing, layer.sides
        material, before_material = layer.sung_brush, layer.waiting_brush
        onset, finish = path[0][0], path[-1][0]
        empty = (0.0, top, 0.0, bottom)
        if self.scanline_mode == "brighten" and self.scanline_brightness == 0:
            return
        before = after = (self.scanline_color, self.scanline_color, material)
        if self.ruby_scanline not in {"reading", "both"}:
            raise ValueError("ruby_scanline must be reading or both")
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

        for strip, (lo, hi, strength, paint) in enumerate(painted_slices()):
            mask = RectangleKeyframes(
                (
                    (onset, empty),
                    *((time, (x + lo, top, x + hi, bottom)) for time, x in path),
                    (finish, empty),
                )
            )

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
                clip=RectangleClip(0, 0, 1, 1, space="local", deform=mask),
            )
            yield copy

    def _burst_plans(
        self, line: LyricLine, nodes: dict[str, SceneObject]
    ) -> Iterator[_Burst]:
        targets = line.query("character")
        sung_end = max(
            (span.end + target.delay for target in targets for span in target.singing),
            default=line.lifetime.start,
        )
        first_host = True
        for index, target in enumerate(targets):
            node = nodes[target.node_id]
            if not isinstance(node, TextObject) or not node.text.strip():
                continue
            for entering, kind, total in (
                (True, self.entry, self.entry_duration),
                (False, self.exit, self.exit_duration),
            ):
                count = _TRANSITION_COUNTS.get(kind)
                if (
                    total <= 0
                    or count is None
                    or (kind == "sparkle" and not first_host)
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
            first_host = False
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
        line_particles: list[SceneObject] = []
        for plan_index, plan in enumerate(plans):
            if (plan.phase != "singing") != transitions:
                continue
            target, node, kind = plan.target, plan.node, plan.kind
            entering, exiting = plan.phase == "entry", plan.phase == "exit"
            em = target.em_size or max(1, target.center.y * 2)
            seed = self.seed + (line.track_index & 0xFFFF) * 0x9E37
            colors = (self.particle_color or Color(255, 255, 255),)
            display = line.lifetime if entering or exiting else None
            if display is not None and self.particle_color is None:
                colors = (
                    (Color(242, 248, 255), Color(191, 223, 255))
                    if kind.startswith("snow")
                    else (Color(255, 183, 197), Color(255, 215, 224))
                )
            if kind == "sparkle":
                bounds = line.layout.body.bounds
                center, box = (
                    Vec2(bounds.center, bounds.middle),
                    Vec2(bounds.width, bounds.height),
                )
                seed += 1 if entering else 3
                destination = line_particles
            else:
                center, box = (
                    node.state.transform.apply(target.center),
                    target.center * 2,
                )
                seed += plan.glyph_index + _burst_seed(kind, entering, exiting)
                destination = additions.setdefault(node.id, [])
            context = ParticleContext(
                f"{node.id}/{self.id}:particle:{plan_index}",
                plan.start,
                seed,
                center,
                line.origin,
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
                        colors=colors,
                        exiting=exiting,
                        display=display,
                    )
                )
                continue
            for index in range(plan.count):
                stream, sample = index % len(colors), index // len(colors)
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
                    duration=plan.duration,
                    color=colors[stream],
                    entering=entering,
                    exiting=exiting,
                    display=display,
                )
                if particle is not None:
                    destination.append(particle)
        return replace(line, children=(*line.children, *line_particles))

    def _display_ornaments(self, line: LyricLine) -> LyricLine:
        """Place transition decorations on the same allocated clock as their text."""
        nodes = {node.id: node for node in _walk(line)}
        additions: dict[str, list[SceneObject]] = {}
        line = self._particles(line, nodes, additions, transitions=True)
        replacements: dict[str, TextObject] = {}
        fade_offsets = (_character_offsets(line, _character_hosts(line), self.exit_duration * self.stagger, entering=False)
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
                if not entering and kind in {"char_fade", "spin_flip"}:
                    start = line.lifetime.end - total * (1 - self.stagger) + fade_offsets[target.node_id]
                    for ink in (node, nodes.get(node.id + "/glow")):
                        if isinstance(ink, TextObject):
                            replacements[ink.id] = _fade_underpaint(replacements.get(ink.id, ink), start)
                    continue
                if kind in {"stretch_in", "stretch_out"}:
                    for alias in (target.node_id, *target.aliases):
                        ink = nodes[alias]
                        if isinstance(ink, TextObject):
                            replacements[alias] = replace(ink, scale_border=True)
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
                            fill=Color(255, 255, 255),
                            blur=0,
                            border=0,
                            shadow=Vec2(),
                            opacity=0.82 ** abs(echo_index),
                        ),
                    )
                    echo = echo.animate(
                        Transform(offset=travel, opacity=envelope, scale=scale, pivot=target.center),
                        duration=travel_duration,
                    )
                    additions.setdefault(node.id, []).append(echo)
        return _insert(line, additions, reserve=False, replacements=replacements)

    def _ornaments(self, line: LyricLine, nodes: dict[str, SceneObject]) -> LyricLine:
        additions: dict[str, list[SceneObject]] = {}
        line = self._particles(line, nodes, additions, transitions=False)
        transition_kinds = {
            "glow_in",
            "glow_out",
            "stretch_in",
            "stretch_out",
            *_TRANSITION_COUNTS,
        }
        if self.entry in transition_kinds or self.exit in transition_kinds | {"char_fade", "spin_flip"}:
            if line._at_placement is None:
                line = self._display_ornaments(line)
            else:
                line = replace(
                    line, _at_placement=(*line._at_placement, self._display_ornaments)
                )
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
            for target, _, unit, box in glyphs:
                group, slot = reading_slots.get(target.node_id, (None, unit))
                track = edges.setdefault(group, {})
                body = group is None
                previous = track.get(slot - 1) if body and not self.reverse_wipe else None
                clock = line.layout.lyrics.units[unit]._body_parts() if body else ((target._reading_span or target.singing[0], 0, 1),)
                passes = _sweeps(clock, target.delay, box,
                                 previous[1] if previous else (),
                                 *clocks[group],
                                 first_pixel=0.5 if body else 0.0, reverse=self.reverse_wipe)
                sweeps[target.node_id] = () if body and unit in reading_only else passes
                first, _ = track.get(slot, (passes, passes))
                track[slot] = first, passes
        ratio = line.layout.script_height / 1080
        width = self.scanline_width or max(1, round(16 * ratio))
        softness = round(8 * ratio) if self.scanline_softness is None else self.scanline_softness
        run_spans = _scanline_run_spans(line) if "scanline" in self.singing else {}
        transformed_band = self.singing == "utopia_scanline"
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
                assert glyph.layout_scale is not None
                scale = glyph.layout_scale
                ink = glyph.ink_bounds or glyph.bounds
                base = painted_nodes[target.node_id]
                sung_id = f"{node.id}/highlight:singing:{unit}"
                sung_piece = painted_nodes.get(sung_id)
                rims = (
                    _hard_rim(painted_nodes.get(sung_id + "/glow"), node.state.border),
                    _hard_rim(painted_nodes.get(node.id + "/glow"), node.state.border),
                )
                pad = max((node.state.border, *(r.state.border for r in rims if r))) + 2
                # Utopia paints inside the transformed fill path’s bounding box.
                vertical_pad = 0 if transformed_band else pad
                top = (ink.top - glyph.bounds.top) / scale.y - vertical_pad
                bottom = (ink.top + ink.height - glyph.bounds.top) / scale.y + vertical_pad
                movements = list(sweeps[target.node_id])
                group, slot = reading_slots.get(target.node_id, (None, unit))
                reach = (width / 2 + pad) * scale.x
                for other, (first, last) in edges[group].items():
                    if other == slot or (group is None and other in reading_only):
                        continue
                    for sweep in last if other < slot else first:
                        overlap = sweep.intersect(ink.left - reach, ink.right + reach)
                        if overlap is not None:
                            movements.append(overlap)
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
                    not self.hook_feather
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
                        not transformed_band
                        and softness > 0
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
                layers.append(_ScanlineLayer(node, material, before_material, sides))
                for layer in layers:
                    strip_top, strip_bottom = top, bottom
                    if layer.sides and not transformed_band:
                        strip_top, strip_bottom = -65536, 65536
                        sung, waiting = layer.sides
                        left_piece, right_piece = (waiting, sung) if self.reverse_wipe else (sung, waiting)
                        for piece, offset, left in (
                            (left_piece, -width / 2, True),
                            (right_piece, width / 2, False),
                        ):
                            replacements[piece.id] = _outside_front(
                                piece, paths, offset, left=left
                            )
                    for index, path in enumerate(paths):
                        for front in self._scanline(
                            layer, index, path, width, softness, strip_top, strip_bottom
                        ):
                            additions.setdefault(layer.drawing.id, []).append(front)
                            aliases.setdefault(target.id, []).append(front.id)
            if not self.stroke_flash or target.role != "character":
                continue
            outline = outline_text(node)
            if outline.path is None:
                continue
            pen = max(2 * node.state.border, (target.em_size or node.font_size) * 0.03)
            path = VectorPath(tuple(
                part for contour in outline.path.contours
                if (ribbon := stroke(flatten(contour), pen)) is not None
                for part in ribbon.contours
            ))

            for index, span in enumerate(line.layout.lyrics.units[unit]._body_singing()):
                onset = span.start + target.delay
                end = min(node.lifetime.end, onset + 0.24)
                if end <= onset:
                    continue
                duration = end - onset

                def flash(base: VisualState, p: float, width: float = pen, window: float = duration) -> VisualState:
                    level = max(0, 1 - p * window / 0.24)
                    return replace(base, opacity=0.85 * level, border=0.3 * width * level)

                copy = PathObject(
                    id=f"{node.id}/{self.id}:flash:{index}",
                    lifetime=Lifetime(onset, end),
                    origin=node.origin,
                    layer=node.layer + 1,
                    state=replace(node.state, opacity=0, fill=Color(255, 255, 255),
                                  outline=Color(255, 255, 255), border=0, blur=0, shadow=Vec2()),
                    path=path,
                ).animate(
                    StateFunction(flash, frozenset({"opacity", "border"})),
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
