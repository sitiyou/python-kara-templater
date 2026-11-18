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
from .lyric_highlights import LyricGlow, LyricHighlights, LyricMaterial
from .lyric_line import (
    LyricAnimationContext,
    LyricLine,
    LyricRule,
    LyricTarget,
    _KaraokePaint,
)
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


def _utopia(context: LyricAnimationContext) -> ScalePulse:
    return ScalePulse(
        peak=1.15,
        peak_at=0.25 if context.duration <= 0.4 else 0.1 / context.duration,
        pivot=context.target.center,
    )


def _zoom(context: LyricAnimationContext) -> StateFunction:
    duration = context.duration
    # Includes a 0.30 s release in the same animation, so the captured baseline is stable.
    note = context.interval.duration if context.interval is not None else duration

    def sample(base: VisualState, p: float) -> VisualState:
        t = p * duration
        amount = (
            1 - (1 - min(1, t / max(note, 0.001))) ** 3
            if t <= note
            else 1 - smooth_rate(min(1, (t - note) / max(0.001, duration - note)))
        )
        return Transform(scale=1 + 0.25 * amount, pivot=context.target.center).sample(
            base, p
        )

    return StateFunction(sample, frozenset({"position", "scale"}))


@dataclass(frozen=True, kw_only=True)
class KaraokeEffects:
    """Compose entry, singing, exit and ornaments as one Track.effects callable.

    All durations are seconds, widths are script pixels; particle_size is a
    fraction of each glyph's measured height. Entry/exit duration includes the
    full stagger span. Zero disables that transition. `none` singing retains
    ordinary wipe; `no_wipe` recolors the whole timed unit at onset. Utopia pulses
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
    stagger: float = 0.55
    sung: Color = Color(255, 90, 111)
    unsung: Color = Color(255, 255, 255)
    material: LyricMaterial = None
    glow: LyricGlow = None
    base_glow: LyricGlow = None
    particle_color: Color | None = Color(255, 255, 255)
    particle_size: float = 0.40
    particle_rate: float = 7
    max_particles: int = 512
    seed: int = 0
    scanline_width: float | None = None
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
        width = 16 if self.scanline_width is None else self.scanline_width
        finite(
            self.entry_duration,
            self.exit_duration,
            self.stagger,
            self.particle_size,
            self.particle_rate,
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
        if min(self.particle_size, self.particle_rate, width) <= 0:
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
        entry_total = min(self.entry_duration, first) if self.entry != "none" else 0
        release = 0.30 if self.singing.startswith("zoom_pulse") else 0
        exit_total = self.exit_duration if self.exit != "none" else 0
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
            base_paint=StatePatch(fill=self.unsung, outline=self.unsung_outline),
            material=self.material,
            glow=self.glow,
            base_glow=self.base_glow,
            hook_feather=self.hook_feather,
            front_color=self.front_color,
        )
        if self.singing == "no_wipe":
            source = highlighter.highlights
            values = source if isinstance(source, tuple) else source(line)
            highlighter = replace(
                highlighter,
                highlights=tuple(
                    replace(
                        h,
                        passes=tuple(
                            replace(p, time=TimeSpan(p.time.start, p.time.start))
                            for p in h.passes
                        ),
                    )
                    for h in values
                ),
            )
        line = highlighter(line)
        line = replace(self, entry_duration=entry_total)._ornaments(line, original)
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
                stagger = (
                    0
                    if kind in {"glow_in", "glow_out"} or len(targets) < 2
                    else total * self.stagger / (len(targets) - 1)
                )
                duration = total - stagger * max(0, len(targets) - 1)
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
                            _zoom,
                            duration=span.end - span.start + release,
                            hold=False,
                        )
                    )
        return replace(
            line,
            _karaoke_paint=_KaraokePaint(
                self.sung,
                self.unsung,
                entry_total,
                exit_total,
                self.singing != "no_wipe",
                self.unsung_outline, self.sung_outline, self.hook_feather,
            ),
        )

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
                plans.append(
                    (
                        target,
                        node,
                        kind,
                        birth,
                        duration,
                        6 if kind == "ripple" else 10,
                        entering,
                        not entering,
                    )
                )
            for segment in target.singing:
                length = segment.end - segment.start
                if length <= 0 or self.decoration == "none":
                    continue
                plans.append(
                    (
                        target,
                        node,
                        self.decoration,
                        segment.start + target.delay,
                        length,
                        max(1, ceil(length * self.particle_rate)),
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
                birth = start + delay
                local = Vec2(
                    random.uniform("x", 0, target.center.x * 2),
                    random.uniform("y", 0, target.center.y * 1.4),
                )
                if kind == "ripple":
                    local = target.center
                if contour_points:
                    local = contour_points[
                        int(random.uniform("point") * len(contour_points))
                    ]
                kind_name = {"assemble_in": "assemble", "dissolve_out": "dissolve"}.get(
                    kind, kind
                )
                color = self.particle_color or (
                    Color(255, 170, 205) if kind == "petal" else self.sung
                )
                particle = ornament(
                    replace(
                        random, birth=birth, position=node.state.transform.apply(local)
                    ),
                    kind_name,
                    size=em * self.particle_size * (0.28 if contour_points else 1),
                    duration=max(0.25, duration - delay)
                    if entering or exiting
                    else 0.75,
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
                for echo_index in (-3, -2, -1, 1, 2, 3):
                    distance = target.center.y * 0.12 * echo_index

                    def envelope(p: float, enter: bool = entering) -> float:
                        q = smooth_rate(p)
                        return (
                            min(1, p * 10) * (1 - q) * sqrt(max(0, 1 - q))
                            if enter
                            else sin(pi * q)
                        )

                    def travel(
                        p: float, enter: bool = entering, x: float = distance
                    ) -> Vec2:
                        return Vec2(
                            x * ((1 - smooth_rate(p)) if enter else smooth_rate(p)), 0
                        )

                    echo = replace(
                        node,
                        id=f"{node.id}/{self.id}:echo:{kind}:{echo_index}",
                        lifetime=Lifetime(birth, birth + total),
                        clock_start=birth,
                        animations=(),
                        clip=None,
                        material=None,
                        reference=None,
                        layer=node.layer - 1,
                        state=replace(
                            node.state,
                            fill=self.sung,
                            outline=self.sung,
                            blur=target.center.y * 0.08,
                            border=1,
                            opacity=0.22,
                        ),
                    )
                    echo = echo.animate(
                        Transform(offset=travel, opacity=envelope), duration=total
                    )
                    additions.setdefault(node.id, []).append(echo)
        # Front and flash copies remain glyph-local and share semantic motion aliases.
        aliases: dict[str, list[str]] = {}
        for target in line.query("character", "ruby"):
            node = nodes[target.node_id]
            if not isinstance(node, TextObject) or not node.text.strip():
                continue
            for index, span in enumerate(target.singing):
                if span.end <= span.start:
                    continue
                start, end = span.start + target.delay, span.end + target.delay
                if "scanline" in self.singing:
                    measured = next(
                        (
                            c
                            for c in line.layout.body.characters
                            if c.object.id == target.node_id
                        ),
                        None,
                    )
                    parent = line.layout.body
                    if measured is None:
                        for ruby in line.layout.ruby:
                            measured = next(
                                (
                                    c
                                    for c in ruby.layout.characters
                                    if c.object.id == target.node_id
                                ),
                                None,
                            )
                            if measured is not None:
                                parent = ruby.layout
                                break
                    left, width = 0.0, max(0.1, target.center.x * 2)
                    if measured is not None:
                        first, last = 0, len(parent.source.text)
                        if target.role == "character":
                            unit = next(
                                u
                                for u in line.layout.lyrics.units
                                if u.start <= measured.start < u.end
                            )
                            first, last = unit.start, unit.end
                        box = parent._sweep_bounds(first, last, measured)
                        assert measured.layout_scale is not None
                        left = (
                            box.left - measured.bounds.left
                        ) / measured.layout_scale.x
                        width = max(0.1, box.width / measured.layout_scale.x)
                    band = self.scanline_width or 16 * line.layout.script_height / 1080

                    onset = local_seconds(start, node.time_origin)
                    finish = local_seconds(end, node.time_origin)
                    empty = (0.0, 0.0, 0.0, 0.0)
                    front = (left - band / 2, -65536.0, left + band / 2, 65536.0)
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
                        id=f"{node.id}/{self.id}:front:{index}",
                        lifetime=node.lifetime,
                        clock_start=node.time_origin,
                        animations=(),
                        material=None,
                        reference=None,
                        layer=node.layer + 2,
                        state=replace(
                            node.state,
                            fill=Color(255, 255, 255),
                            outline=self.sung,
                            blur=1.5,
                            border=2,
                        ),
                        clip=RectangleClip(0, 0, 1, 1, space="local", deform=mask),
                    )
                    additions.setdefault(node.id, []).append(copy)
                    aliases.setdefault(target.id, []).append(copy.id)
                if self.stroke_flash and target.role == "character":
                    copy = replace(
                        node,
                        id=f"{node.id}/{self.id}:flash:{index}",
                        lifetime=node.lifetime,
                        clock_start=node.time_origin,
                        animations=(),
                        clip=None,
                        material=None,
                        reference=None,
                        layer=node.layer + 1,
                        state=replace(
                            node.state,
                            fill=self.sung,
                            outline=Color(255, 255, 255),
                            blur=0.5,
                            border=max(1, node.state.border),
                        ),
                    )
                    outline = outline_text(node)
                    if outline.path is None:
                        continue
                    strokes = [
                        stroke(flatten(contour), max(1, node.state.border))
                        for contour in outline.path.contours
                    ]
                    copy = PathObject(
                        id=copy.id,
                        lifetime=node.lifetime,
                        clock_start=node.time_origin,
                        origin=node.origin,
                        layer=node.layer + 1,
                        state=replace(
                            node.state,
                            opacity=0,
                            fill=Color(255, 255, 255),
                            border=0,
                            blur=0.35,
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

                    def flash(base: VisualState, p: float) -> VisualState:
                        return replace(base, opacity=(1 - p) ** 2)

                    copy = copy.animate(
                        StateFunction(flash, frozenset({"opacity"})),
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
