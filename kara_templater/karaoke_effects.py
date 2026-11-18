"""A complete, configurable karaoke animation recipe using ordinary Scene objects."""

from collections.abc import Iterator
from dataclasses import dataclass, replace
from functools import partial
from math import ceil, pi, sin, sqrt
from typing import Literal, get_args

from ._karaoke_motion import transition
from ._karaoke_sprites import ornament
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
from .paint_fields import LinearGradient, PaintField
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
_PARTICLES = frozenset({"sparkle", "ripple", "note", "petal", "snow", "snow_solid"})


def _walk(node: SceneObject) -> Iterator[SceneObject]:
    yield node
    if isinstance(node, ObjectGroup):
        for child in node.children:
            yield from _walk(child)


def _insert(line: LyricLine, additions: dict[str, list[SceneObject]]) -> LyricLine:
    windows = tuple(
        TimeSpan(node.lifetime.start, node.lifetime.end)
        for nodes in additions.values()
        for node in nodes
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
    fraction of each glyph's measured height. Entry/exit duration includes the
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
                    duration - total if not entering and kind == "glow_out" else 0.0
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
                            transition, kind=kind, entering=entering, seed=self.seed
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
        before = after = (self.scanline_color, self.scanline_color)
        if self.scanline_mode not in {"role", "color"}:
            before = (
                _brighten(self.unsung, self.scanline_brightness),
                _brighten(
                    self.unsung_outline or node.state.outline, self.scanline_brightness
                ),
            )
            after = (
                _brighten(self.sung, self.scanline_brightness),
                _brighten(
                    self.sung_outline or node.state.outline, self.scanline_brightness
                ),
            )
            if self.scanline_mode == "follow_before":
                after = before
            elif self.scanline_mode == "follow_after":
                before = after

        def painted_slices() -> Iterator[
            tuple[float, float, float, tuple[Color, Color]]
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
                material=material,
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

    def _ornaments(self, line: LyricLine, nodes: dict[str, SceneObject]) -> LyricLine:
        additions: dict[str, list[SceneObject]] = {}
        plans: list[
            tuple[LyricTarget, TextObject, str, float, float, int, bool, bool]
        ] = []
        targets = line.query("character")
        for index, target in enumerate(targets):
            node = nodes[target.node_id]
            if not isinstance(node, TextObject) or not node.text.strip():
                continue
            for entering, kind, total in (
                (True, self.entry, self.entry_duration),
                (False, self.exit, self.exit_duration),
            ):
                if total <= 0 or kind not in _PARTICLES | {
                    "assemble_in",
                    "dissolve_out",
                }:
                    continue
                step = total * self.stagger / max(1, len(targets) - 1)
                duration = total * (1 - self.stagger) if len(targets) > 1 else total
                birth = (
                    line.lifetime.start + index * step
                    if entering
                    else max(
                        line.lifetime.start, line.lifetime.end - total + index * step
                    )
                )
                if kind == "petal":
                    duration = total * 1.5
                plans.append(
                    (
                        target,
                        node,
                        kind,
                        birth,
                        duration,
                        3
                        if kind in {"ripple", "note", "petal", "snow", "snow_solid"}
                        else 10,
                        entering,
                        not entering,
                    )
                )
            for segment in target.singing:
                length = segment.end - segment.start
                if length <= 0 or self.decoration == "none":
                    continue
                duration, count = _SING_BURSTS[self.decoration]
                if self.particle_rate is not None and self.decoration != "ripple":
                    count = max(1, ceil(length * self.particle_rate))
                plans.append(
                    (
                        target,
                        node,
                        self.decoration,
                        segment.start + target.delay,
                        duration,
                        count,
                        False,
                        False,
                    )
                )
        if sum(p[5] for p in plans) > self.max_particles:
            raise ValueError("karaoke particle budget exceeded before construction")
        for plan_index, (
            target,
            node,
            kind,
            start,
            duration,
            count,
            entering,
            exiting,
        ) in enumerate(plans):
            em = max(1, target.center.y * 2)
            contour_points: tuple[Vec2, ...] = ()
            if kind in {"assemble_in", "dissolve_out"}:
                outline = outline_text(node)
                if outline.path is not None:
                    contour_points = tuple(
                        point
                        for contour in outline.path.contours
                        for point in flatten(contour).points
                    )
            for index in range(count):
                name = f"{node.id}/{self.id}:particle:{plan_index}:{index}"
                random = ParticleContext(name, start, self.seed, Vec2(), line.origin)
                delay = (
                    duration
                    * index
                    / max(1, count)
                    * (0.45 if entering or exiting else 0.85)
                )
                if kind == "ripple":
                    delay = index * duration / 4
                elif kind in {"petal", "snow", "snow_solid"}:
                    delay = random.uniform("delay") * min(
                        duration / 2, 0.11 if kind == "petal" else 0.16
                    )
                birth = start + delay
                local = Vec2(
                    random.uniform("x", 0, target.center.x * 2),
                    random.uniform("y", 0, target.center.y * 1.4),
                )
                if kind in {"ripple", "petal", "snow", "snow_solid"}:
                    local = target.center
                if kind == "note":
                    local = Vec2(
                        target.center.x * random.uniform("x", 0.2, 1.8),
                        target.center.y * 0.30,
                    )
                elif kind in {"sparkle", "twinkle"}:
                    local = Vec2(
                        local.x, target.center.y * random.uniform("star_y", -0.24, 1.60)
                    )
                if contour_points:
                    local = contour_points[
                        int(random.uniform("point") * len(contour_points))
                    ]
                kind_name = {"assemble_in": "assemble", "dissolve_out": "dissolve"}.get(
                    kind, kind
                )
                color = self.particle_color or Color(255, 255, 255)
                if self.particle_color is None and (entering or exiting):
                    pair = (
                        (Color(242, 248, 255), Color(191, 223, 255))
                        if kind.startswith("snow")
                        else (Color(255, 183, 197), Color(255, 215, 224))
                    )
                    color = pair[index % 2]
                particle = ornament(
                    replace(
                        random, birth=birth, position=node.state.transform.apply(local)
                    ),
                    kind_name,
                    box=target.center * 2,
                    size=em * self.particle_size * (0.28 if contour_points else 1),
                    duration=duration - delay,
                    color=color,
                    entering=entering,
                    exiting=exiting,
                )
                additions.setdefault(node.id, []).append(particle)
        # Horizontal glow echoes have their own envelope, beneath the sharp glyph.
        for target in line.query("character", "ruby"):
            node = nodes[target.node_id]
            if not isinstance(node, TextObject) or not node.text.strip():
                continue
            for entering, kind, total in (
                (True, self.entry, self.entry_duration),
                (False, self.exit, self.exit_duration),
            ):
                if kind not in {"glow_in", "glow_out"} or total <= 0:
                    continue
                birth = line.lifetime.start if entering else line.lifetime.end - total
                travel_duration = total * (1 - self.stagger)
                for echo_index in (*range(-14, 0), *range(1, 15)):
                    distance = node.font_size * 0.12 * echo_index

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
        if "scanline" not in self.singing and not self.stroke_flash:
            return _insert(line, additions)
        # Front and flash copies remain glyph-local and share semantic motion aliases.
        aliases: dict[str, list[str]] = {}
        for target, glyph, _, box in line._glyph_regions(automatic=True):
            node = nodes[target.node_id]
            if not isinstance(node, TextObject) or not node.text.strip():
                continue
            material: PaintField | None = None
            if self.scanline_mode == "role":
                material = _resolve_material(self.scanline_material, line, target)
                if isinstance(material, LinearGradient) and material.fill is not None:
                    material = replace(material, outline=material.fill)
            for index, span in enumerate(target.singing):
                if span.end <= span.start:
                    continue
                start, end = span.start + target.delay, span.end + target.delay
                if "scanline" in self.singing:
                    assert glyph.layout_scale is not None
                    scale = glyph.layout_scale.x
                    left = (box.left - glyph.bounds.left) / scale
                    ink = glyph.ink_bounds or glyph.bounds
                    pad = node.state.border + 2
                    top = (ink.top - glyph.bounds.top) / glyph.layout_scale.y - pad
                    bottom = (
                        ink.top + ink.height - glyph.bounds.top
                    ) / glyph.layout_scale.y + pad
                    for front in self._scanline(
                        line,
                        node,
                        index,
                        start,
                        end,
                        left,
                        box.width / scale,
                        top,
                        bottom,
                        material,
                    ):
                        additions.setdefault(node.id, []).append(front)
                        aliases.setdefault(target.id, []).append(front.id)
                if self.stroke_flash and target.role == "character":
                    outline = outline_text(node)
                    if outline.path is None:
                        continue
                    pen = max(2 * node.state.border, node.font_size * 0.03)
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
