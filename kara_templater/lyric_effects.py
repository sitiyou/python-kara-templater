"""Reusable lyric visual factories that expand into ordinary Scene objects."""

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Literal

from .geometry import Vec2, finite
from .lyric_line import LyricAnimationContext, LyricLine
from .particles import ParticleContext
from .scene import Lifetime, ObjectGroup, SceneObject, TextObject
from .scene_animation import (
    FadeOut,
    StateAnimation,
    StatePatch,
    TimeSpan,
    Transform,
    _resolve_pivot,
    linear_rate,
    smooth_rate,
)


def lyric_effects(
    *effects: Callable[[LyricLine], LyricLine],
) -> Callable[[LyricLine], LyricLine]:
    """Compose built-in or custom lyric factories in the supplied order.

    Pass the result as an entry in Track.effects. Each factory runs once on the prepared
    line; it must retain its identity. Timing/animation evaluation stays in Scene.
    """
    def apply(line: LyricLine) -> LyricLine:
        identity = line.id
        for effect in effects:
            line = effect(line)
            if not isinstance(line, LyricLine) or line.id != identity:
                raise ValueError("lyric effects must preserve line identity")
        return line

    return apply


@dataclass(frozen=True, kw_only=True)
class ScatterOut:
    """A seeded lyric animation factory for rotating, drifting glyph exits.

    Pass to LyricRule.animation with an exit/after_singing anchor. spread is the
    horizontal displacement range, rise the upward displacement, rotation the
    maximum added angle; units are script pixels/degrees. No timing is hidden in
    this factory: duration, pause and stagger belong to the rule.
    """

    spread: float = 24
    rise: float = 36
    rotation: float = 30
    scale: float = 0.85
    seed: int = 0

    def __post_init__(self) -> None:
        finite(self.spread, self.rise, self.rotation, self.scale)
        if self.spread < 0 or self.rotation < 0 or self.scale <= 0 or type(self.seed) is not int:
            raise ValueError("invalid scatter range, scale or seed")

    def __call__(self, timing: LyricAnimationContext) -> Transform:
        """Resolve deterministic per-target variation into a common animation."""
        context = ParticleContext(timing.target.id, 0, self.seed, Vec2(), timing.line.origin)
        offset = Vec2(context.uniform("drift", -self.spread, self.spread),
                      -self.rise * context.uniform("rise", 0.7, 1.3))
        angle = context.uniform("angle", -self.rotation, self.rotation)
        return Transform(
            offset=lambda p: offset * smooth_rate(p),
            rotation=lambda p: angle * smooth_rate(p),
            scale=lambda p: 1 + (self.scale - 1) * smooth_rate(p),
            opacity=lambda p: 1 - smooth_rate(p),
        )


@dataclass(frozen=True, kw_only=True)
class LyricEcho:
    """Emit offset, fading copies at each character/ruby singing onset.

    Copies use the selected glyph's prepared static appearance, optionally
    overridden by paint. They deliberately show the full glyph, without its
    sweep mask, material, reference or existing animation; this is an onset echo,
    not a historical motion trail. Parent line/syllable transforms still apply.
    Ordinary lyric rules continue to target the original glyph, not its echoes.

    spacing/duration are seconds; offset is the parent-space distance between
    successive copies. opacity multiplies original opacity, then decay reduces
    each later copy. animation uses the common animation protocol, with the
    measured target center as default pivot, and is stretched to duration.
    The default is a linear fade, using native ASS where available. delay shifts
    all copy births relative to the onset; negative values allow approaching
    copies before singing, but no copy may precede Scene zero. Required display
    is extended without changing singing times.
    """

    id: str = "echo"
    target: Literal["character", "ruby"] = "character"
    count: int = 3
    spacing: float = 0.06
    duration: float = 0.45
    offset: Vec2 = Vec2(0, -8)
    opacity: float = 0.35
    decay: float = 0.65
    paint: StatePatch = StatePatch()
    max_copies: int = 256
    animation: StateAnimation = FadeOut(linear_rate)
    delay: float = 0

    def __post_init__(self) -> None:
        finite(self.spacing, self.duration, self.opacity, self.decay, self.delay)
        if not isinstance(self.animation, StateAnimation):
            raise TypeError("echo animation must implement StateAnimation")
        if not self.id or self.target not in ("character", "ruby"):
            raise ValueError("echo needs an id and a character/ruby target")
        if type(self.count) is not int or self.count < 1:
            raise ValueError("echo count must be a positive integer")
        if type(self.max_copies) is not int or self.max_copies < 1:
            raise ValueError("echo max_copies must be a positive integer")
        if self.spacing < 0 or self.duration <= 0:
            raise ValueError("echo spacing must be nonnegative and duration positive")
        if not 0 <= self.opacity <= 1 or not 0 <= self.decay <= 1:
            raise ValueError("echo opacity and decay must be in 0..1")
        if not self.paint.channels <= {"fill", "outline", "opacity", "border", "blur", "shadow"}:
            raise ValueError("echo paint cannot change geometry")

    def __call__(self, line: LyricLine) -> LyricLine:
        """Expand a bounded onset schedule into copies under the glyph's parent."""
        if line.coverage is not None:
            raise ValueError("lyric echo requires ordinary clip-mode visuals")
        nodes: dict[str, SceneObject] = {}

        def collect(node: SceneObject) -> None:
            nodes[node.id] = node
            if isinstance(node, ObjectGroup):
                for child in node.children:
                    collect(child)

        collect(line)
        schedule = tuple(
            (target, index, span)
            for target in line.query(self.target)
            for node in (nodes[target.node_id],)
            for index, span in enumerate(target.singing)
            if span.end > span.start
            and isinstance(node, TextObject)
            and node.text.strip()
        )
        if len(schedule) * self.count > self.max_copies:
            raise ValueError("lyric echo copy budget exceeded before copying")
        additions: dict[str, list[SceneObject]] = {}
        windows = list(line.required_display)
        for target, segment, span in schedule:
            node = nodes[target.node_id]
            state = self.paint.interpolate(node.state, 1)
            for index in range(self.count):
                identity = f"{target.node_id}/{self.id}:{segment}:{index}"
                if identity in nodes:
                    raise ValueError(f"duplicate lyric echo id: {identity}")
                birth = span.start + target.delay + self.delay + index * self.spacing
                if birth < 0:
                    raise ValueError("lyric echo birth cannot precede Scene zero")
                window = Lifetime(birth, birth + self.duration)
                echo = replace(
                    node, id=identity, lifetime=window, clock_start=birth,
                    animations=(), reference=None, clip=None, material=None,
                    layer=node.layer - 1,
                    state=replace(
                        state,
                        position=state.position + self.offset * (index + 1),
                        opacity=state.opacity * self.opacity * self.decay**index,
                    ),
                ).animate(_resolve_pivot(self.animation, target.center), duration=self.duration)
                additions.setdefault(node.id, []).append(echo)
                windows.append(TimeSpan(window.start, window.end))

        def insert(node: SceneObject) -> SceneObject:
            if not isinstance(node, ObjectGroup):
                return node
            return replace(node, children=tuple(
                item
                for child in node.children
                for item in (insert(child), *additions.get(child.id, ()))
            ))

        result = insert(line)
        assert isinstance(result, LyricLine)
        result = replace(result, required_display=tuple(windows))
        if windows:
            result = result.with_display(Lifetime(
                min(line.lifetime.start, *(span.start for span in windows)),
                max(line.lifetime.end, *(span.end for span in windows)),
            ))
        return result
