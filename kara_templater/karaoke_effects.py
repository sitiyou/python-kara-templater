"""A complete, configurable karaoke animation recipe using ordinary Scene objects."""

from collections.abc import Iterator
from dataclasses import dataclass, replace
from functools import partial
from math import ceil, pi, sin, sqrt
from typing import Literal, get_args

from ._karaoke_motion import stretch, transition
from ._karaoke_sprites import ornament, star_burst
from .composition import Color
from .geometry import Vec2, VectorPath, finite
from .lyric_highlights import (
    LyricGlow,
    LyricHighlights,
    LyricMaterial,
    _resolve_material,
)
from .lyric_line import (
    LyricAnimationContext,
    LyricLine,
    LyricRule,
    LyricTarget,
    _KaraokePaint,
)
from .model import Box
from .paint_fields import ColorRamp, LinearGradient, PaintField
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
    line: LyricLine, additions: dict[str, list[SceneObject]], *, reserve: bool = True
) -> LyricLine:
    windows = tuple(
        TimeSpan(node.lifetime.start, node.lifetime.end)
        for nodes in additions.values()
        for node in nodes
        if reserve and node.lifetime != line.lifetime
    )

    def visit(node: SceneObject) -> SceneObject:
        if not isinstance(node, ObjectGroup):
            return node
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


def _transition_window(kind: str, configured: float, *, entering: bool) -> float:
    if kind == "none" or configured == 0:
        return 0
    if kind == "utopia":
        return 0.70 if entering else 0.75
    if kind in {"char_fade", "char_drip", "spin_flip"}:
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


def _zoom(context: LyricAnimationContext, *, level: int) -> StateFunction:
    duration = context.duration
    # Includes a 0.30 s release in the same animation, so the captured baseline is stable.
    note = context.interval.duration if context.interval is not None else duration

    def sample(base: VisualState, p: float) -> VisualState:
        t = p * duration
        amount = (
            1 - (1 - min(1, t / max(note, 0.001))) ** max(1, level)
            if t <= note
            else 1 - min(1, (t - note) / 0.30) ** max(1, level)
        )
        return Transform(scale=1 + 0.25 * amount, pivot=context.target.center).sample(
            base, p
        )

    return StateFunction(sample, frozenset({"position", "scale"}))


def _brighten(color: Color, strength: float) -> Color:
    """Raise HSV value toward white while retaining hue and saturation."""
    channels = (color.red, color.green, color.blue)
    value = max(channels)
    raised = value + (255 - value) * strength
    if value == 0:
        return Color(*(round(raised) for _ in channels))
    return Color(*(round(c * raised / value) for c in channels))


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


@dataclass(frozen=True)
class _Sweep:
    start: float
    end: float
    left: float
    right: float

    def intersect(self, left: float, right: float) -> "_Sweep | None":
        width = self.right - self.left
        a, b = max(self.left, left), min(self.right, right)
        if a >= b or width <= 0:
            return None
        dt = (self.end - self.start) / width
        return _Sweep(
            self.start + (a - self.left) * dt, self.start + (b - self.left) * dt, a, b
        )


def _sweeps(target: LyricTarget, bounds: Box) -> tuple[_Sweep, ...]:
    return tuple(
        _Sweep(
            span.start + target.delay,
            span.end + target.delay,
            bounds.left,
            bounds.right,
        )
        for span in target.singing
        if span.end > span.start
    )


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
    for index in range(count):
        left = index * step - half
        distance = abs(left + step / 2)
        yield (
            left,
            left + step,
            smooth_rate(min(1, max(0, (half - distance) / softness))),
        )


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
    decoration: KaraokeDecoration = "none"
    entry_duration: float = 0.3
    exit_duration: float = 0.3
    stagger: float = 7 / 12
    sung: Color = Color(255, 90, 111)
    unsung: Color = Color(255, 255, 255)
    material: LyricMaterial = None
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
    scanline_material: LyricMaterial = None
    scanline_brightness: float = 0.60
    scanline_color: Color = Color(255, 255, 255)
    hook_feather: float = 0
    front_color: Color | None = None
    unsung_outline: Color | None = None
    sung_outline: Color | None = None
    stroke_flash: bool = False
    id: str = "karaoke"

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
            base_paint=StatePatch(fill=self.unsung, outline=self.unsung_outline),
            material=self.material,
            glow=self.glow,
            base_glow=self.base_glow,
            hook_feather=self.hook_feather,
            front_color=self.front_color,
        )
        line = highlighter(line)
        line = replace(
            self, entry_duration=entry_total, exit_duration=exit_total
        )._ornaments(line, original)
        for entering, kind, total in (
            (True, self.entry, entry_total),
            (False, self.exit, exit_total),
        ):
            if kind == "none" or total == 0:
                continue
            anchor = "enter" if entering else "exit"
            roles = (
                ("line",)
                if kind in {"fade", "slide_in", "slide_out", "rise"}
                else ("character", "ruby")
            )
            for role in roles:
                targets = line.query(role)
                if not entering and kind == "utopia":
                    for index, target in enumerate(targets):
                        if not target.singing:
                            continue
                        done = max(span.end for span in target.singing) + target.delay
                        following = (
                            targets[index + 1] if index + 1 < len(targets) else None
                        )
                        following_done = (
                            max(
                                (
                                    span.end + following.delay
                                    for span in following.singing
                                ),
                                default=done,
                            )
                            if following is not None
                            else line.lifetime.end - total
                        )
                        departure = max(done + release, following_done)

                        def following_anchor(
                            _line: LyricLine,
                            _target: LyricTarget,
                            at: float = departure,
                        ) -> tuple[TimeSpan, ...]:
                            return (TimeSpan(at, at),)

                        line = line.schedule(
                            LyricRule(
                                target,
                                following_anchor,
                                partial(
                                    transition,
                                    kind=kind,
                                    entering=False,
                                    seed=self.seed,
                                    zoom_pivot=self.singing.startswith("zoom_pulse"),
                                ),
                                duration=total,
                            )
                        )
                    continue
                if role == "line":
                    duration, stagger = total, 0.0
                else:
                    spread = total * (2 / 7 if kind == "utopia" else self.stagger)
                    duration = total - spread
                    stagger = (
                        spread / max(1, len(targets) - 1)
                        if kind not in {"glow_in", "glow_out"}
                        else 0.0
                    )
                # Studio's synchronized glow finishes its travel early, then holds.
                offset = (
                    duration - total
                    if not entering and (kind == "glow_out" or len(targets) == 1)
                    else 0.0
                )
                if entering and stagger:
                    # A delayed entry must hide its glyph while earlier glyphs arrive.
                    # Releasing this clip restores the unmodified baseline at entry onset.
                    line = line.schedule(
                        *(
                            LyricRule(
                                target,
                                "enter",
                                Transform(opacity=0),
                                duration=index * stagger,
                                hold=False,
                            )
                            for index, target in enumerate(targets)
                            if index
                        )
                    )
                line = line.schedule(
                    LyricRule(
                        targets,
                        anchor,
                        partial(
                            transition,
                            kind=kind,
                            entering=entering,
                            seed=self.seed,
                            zoom_pivot=self.singing.startswith("zoom_pulse"),
                        ),
                        duration=duration,
                        stagger=stagger,
                        offset=offset,
                    )
                )
        if self.singing.startswith("utopia"):
            line = line.schedule(
                *(LyricRule(role, "singing", _utopia) for role in ("character", "ruby"))
            )
        if self.singing.startswith("zoom_pulse"):
            for target in line.query("character", "ruby"):
                for span_index, span in enumerate(target.singing):
                    if span.end <= span.start:
                        continue

                    def anchor(
                        _line: LyricLine,
                        _target: LyricTarget,
                        start: float = span.start + target.delay,
                        end: float = span.end + target.delay,
                    ) -> tuple[TimeSpan, ...]:
                        return (TimeSpan(start, end),)

                    release = (
                        min(
                            0.30,
                            max(0, target.singing[span_index + 1].start - span.end),
                        )
                        if span_index + 1 < len(target.singing)
                        else 0.30
                    )
                    line = line.schedule(
                        LyricRule(
                            target,
                            anchor,
                            partial(_zoom, level=self.zoom_pulse_curve_level),
                            duration=span.end - span.start + release,
                            hold=False,
                        )
                    )
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
            ),
        )

    def _scanline(
        self,
        line: LyricLine,
        node: TextObject,
        index: int,
        start: float,
        end: float,
        left: float,
        width: float,
        top: float,
        bottom: float,
        material: PaintField | None,
    ) -> Iterator[TextObject]:
        ratio = line.layout.script_height / 1080
        band = self.scanline_width or max(1, round(16 * ratio))
        softness = (
            max(1, round(8 * ratio))
            if self.scanline_softness is None
            else self.scanline_softness
        )

        onset = local_seconds(start, node.time_origin)
        finish = local_seconds(end, node.time_origin)
        empty = (0.0, top, 0.0, bottom)
        if self.scanline_mode == "brighten" and self.scanline_brightness == 0:
            return
        before = after = (self.scanline_color, self.scanline_color, material)
        if self.scanline_mode not in {"role", "color"}:
            before = (
                _brighten(self.unsung, self.scanline_brightness),
                _brighten(
                    self.unsung_outline or node.state.outline, self.scanline_brightness
                ),
                None,
            )
            after = (
                _brighten(self.sung, self.scanline_brightness),
                _brighten(
                    self.sung_outline or node.state.outline, self.scanline_brightness
                ),
                material,
            )
            if self.scanline_mode == "follow_before":
                after = before
            elif self.scanline_mode == "follow_after":
                before = after

        def painted_slices() -> Iterator[
            tuple[float, float, float, tuple[Color, Color, PaintField | None]]
        ]:
            for lo, hi, strength in _scanline_slices(band, softness):
                if after == before or lo >= 0:
                    yield lo, hi, strength, before
                elif hi <= 0:
                    yield lo, hi, strength, after
                else:
                    yield lo, 0, strength, after
                    yield 0, hi, strength, before

        for strip, (lo, hi, strength, paint) in enumerate(painted_slices()):
            front = (left + lo, top, left + hi, bottom)
            back = (front[0] + width, front[1], front[2] + width, front[3])
            mask = RectangleKeyframes(
                (
                    (onset, empty),
                    (onset, front),
                    (finish, back),
                    (finish, empty),
                )
            )

            copy = replace(
                node,
                id=f"{node.id}/{self.id}:front:{index}:{strip}",
                lifetime=node.lifetime,
                clock_start=node.time_origin,
                animations=(),
                material=paint[2],
                reference=None,
                layer=node.layer + 2,
                state=replace(
                    node.state,
                    fill=paint[0],
                    outline=paint[1],
                    blur=0,
                    shadow=Vec2(),
                    opacity=node.state.opacity * strength,
                ),
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
                if kind in {"stretch_in", "stretch_out"}:
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
                if kind not in {"glow_in", "glow_out"}:
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
                        return Vec2(
                            x
                            * (
                                1 - 0.25 * smooth_rate(p)
                                if enter
                                else 1 + 0.9 * smooth_rate(p)
                            ),
                            0,
                        )

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
                        Transform(offset=travel, opacity=envelope),
                        duration=travel_duration,
                    )
                    additions.setdefault(node.id, []).append(echo)
        return _insert(line, additions, reserve=False)

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
        if self.entry in transition_kinds or self.exit in transition_kinds:
            if line._at_placement is None:
                line = self._display_ornaments(line)
            else:
                line = replace(
                    line, _at_placement=(*line._at_placement, self._display_ornaments)
                )
        if "scanline" not in self.singing and not self.stroke_flash:
            return _insert(line, additions)
        # Front and flash copies remain glyph-local and share semantic motion aliases.
        aliases: dict[str, list[str]] = {}
        painted_nodes = (
            {n.id: n for n in _walk(line)} if self.material is not None else {}
        )
        glyphs = tuple(line._glyph_regions(automatic=True))
        # At unit boundaries the moving band can still intersect ink on either side.
        # Use the nearest edge glyph's measured sweep when tracking across added spacing.
        body_edges: dict[int, tuple[tuple[_Sweep, ...], tuple[_Sweep, ...]]] = {}
        if "scanline" in self.singing:
            for target, _, unit, box in glyphs:
                if target.role == "character":
                    passes = _sweeps(target, box)
                    first, _ = body_edges.get(unit, (passes, passes))
                    body_edges[unit] = first, passes
        for target, glyph, unit, box in glyphs:
            node = nodes[target.node_id]
            if not isinstance(node, TextObject) or not node.text.strip():
                continue
            material: PaintField | None = None
            if self.scanline_mode == "role":
                material = _resolve_material(self.scanline_material, line, target)
                if isinstance(material, LinearGradient) and material.fill is not None:
                    material = replace(material, outline=material.fill)
            elif self.scanline_mode in {"follow_after", "brighten"} and painted_nodes:
                for alias in target.aliases:
                    source = painted_nodes[alias].material
                    if isinstance(source, LinearGradient):
                        material = _brighten_gradient(source, self.scanline_brightness)
                        break
            if "scanline" in self.singing:
                assert glyph.layout_scale is not None
                scale = glyph.layout_scale
                ink = glyph.ink_bounds or glyph.bounds
                pad = node.state.border + 2
                top = (ink.top - glyph.bounds.top) / scale.y - pad
                bottom = (ink.top + ink.height - glyph.bounds.top) / scale.y + pad
                movements = list(_sweeps(target, box))
                if target.role == "character":
                    radius = self.scanline_width or max(
                        1, round(16 * line.layout.script_height / 1080)
                    )
                    reach = (radius / 2 + pad) * scale.x
                    for other, (first, last) in body_edges.items():
                        if other == unit:
                            continue
                        for sweep in last if other < unit else first:
                            overlap = sweep.intersect(
                                ink.left - reach, ink.right + reach
                            )
                            if overlap is not None:
                                movements.append(overlap)
                for index, sweep in enumerate(movements):
                    for front in self._scanline(
                        line,
                        node,
                        index,
                        sweep.start,
                        sweep.end,
                        (sweep.left - glyph.bounds.left) / scale.x,
                        (sweep.right - sweep.left) / scale.x,
                        top,
                        bottom,
                        material,
                    ):
                        additions.setdefault(node.id, []).append(front)
                        aliases.setdefault(target.id, []).append(front.id)
            for index, span in enumerate(target.singing):
                if span.end <= span.start:
                    continue
                start = span.start + target.delay
                if self.stroke_flash and target.role == "character":
                    outline = outline_text(node)
                    if outline.path is None:
                        continue
                    pen = max(
                        2 * node.state.border, (target.em_size or node.font_size) * 0.03
                    )
                    strokes = [
                        stroke(flatten(contour), pen)
                        for contour in outline.path.contours
                    ]
                    copy = PathObject(
                        id=f"{node.id}/{self.id}:flash:{index}",
                        lifetime=node.lifetime,
                        clock_start=node.time_origin,
                        origin=node.origin,
                        layer=node.layer + 1,
                        state=replace(
                            node.state,
                            opacity=0,
                            fill=Color(255, 255, 255),
                            border=0,
                            blur=0,
                            shadow=Vec2(),
                            outline=Color(255, 255, 255),
                        ),
                        path=VectorPath(
                            tuple(
                                c
                                for path in strokes
                                if path is not None
                                for c in path.contours
                            )
                        ),
                    )

                    def flash(
                        base: VisualState, p: float, width: float = pen
                    ) -> VisualState:
                        return replace(
                            base, opacity=0.85 * (1 - p), border=0.3 * width * (1 - p)
                        )

                    copy = copy.animate(
                        StateFunction(flash, frozenset({"opacity", "border"})),
                        at=start - node.time_origin,
                        duration=0.24,
                    )
                    additions.setdefault(node.id, []).append(copy)
                    aliases.setdefault(target.id, []).append(copy.id)
        result = _insert(line, additions)
        return replace(
            result,
            targets=tuple(
                replace(t, aliases=(*t.aliases, *aliases.get(t.id, ())))
                for t in result.targets
            ),
        )
