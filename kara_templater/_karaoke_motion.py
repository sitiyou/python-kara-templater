"""Studio-style motion expressed through the existing StateAnimation protocol."""

from collections.abc import Callable
from dataclasses import dataclass, replace
from math import cos, pi, radians, sin, tan

from .easing import ease_out
from .geometry import Vec2
from .lyric_line import LyricAnimationContext
from .scene_animation import (
    Channel,
    StateAnimation,
    StateFunction,
    Transform,
    VisualState,
    linear_rate,
    smooth_rate,
)


@dataclass(frozen=True)
class Slide:
    """Studio translation keeps its short entry reveal on a separate curve."""

    offset: Vec2
    entering: bool
    fast_reveal: bool = True
    rate: Callable[[float], float] = smooth_rate

    @property
    def channels(self) -> frozenset[Channel]:
        return frozenset(("position", "scale", "rotation", "skew", "opacity"))

    def sample(self, base: VisualState, progress: float) -> VisualState:
        q = self.rate(progress)
        distance = 1 - q if self.entering else q
        alpha = (
            min(1.0, 4 * progress)
            if self.entering and self.fast_reveal
            else 1 - distance
        )
        return replace(
            base,
            position=base.position + self.offset * distance,
            opacity=base.opacity * alpha,
        )


def _scatter(index: int, seed: int, em: float) -> tuple[Vec2, float]:
    def channel(salt: int) -> float:
        # Studio indexes its scatter fan by glyph order using unsigned 32-bit arithmetic.
        value = ((index + seed) * 0x85EBCA77 + salt * 0xC2B2AE3D) & 0xFFFFFFFF
        value = ((value ^ (value >> 15)) * 0x2545F491) & 0xFFFFFFFF
        return ((value ^ (value >> 13)) & 0xFFFFFF) / 0x1000000

    angle = 2 * pi * channel(1)
    travel = em * 2.2 * (0.55 + 0.45 * channel(2))
    return Vec2(cos(angle), sin(angle)) * travel, (channel(3) - 0.5) * 720


def transition(
    context: LyricAnimationContext,
    kind: str,
    entering: bool,
    seed: int,
) -> StateAnimation:
    target = context.target
    center = target.center
    em = max(1, center.y * 2)
    targets = context.line.query(target.role)
    index = targets.index(target)
    spread = 0 if len(targets) < 2 else 2 * index / (len(targets) - 1) - 1
    if kind == "char_fade":
        return Slide(Vec2(), entering, fast_reveal=False, rate=linear_rate)
    if kind == "fade":
        return Slide(Vec2(), entering, fast_reveal=False, rate=ease_out)
    if kind in {"slide_in", "slide_out"}:
        return Slide(Vec2(-max(36, 0.9 * em), 0), entering, fast_reveal=False, rate=ease_out)
    if kind == "wave_in":
        return Slide(Vec2(0, max(24, em * 0.5)), entering)
    if kind == "rise":
        distance = max(18, em * 0.35)
        return Slide(
            Vec2(0, distance if entering else -distance),
            entering,
            fast_reveal=False,
            rate=ease_out,
        )
    if kind == "tracking_in":
        return Slide(Vec2(spread * em * 1.6, 0), entering)
    travel, spin = _scatter(index, seed, em) if kind == "scatter_out" else (Vec2(), 0.0)

    def sample(base: VisualState, p: float) -> VisualState:
        q = smooth_rate(p)
        remaining = 1 - q if entering else q
        opacity = min(1, p * 4) if entering else 1 - q
        offset, scale, rotation, shear, blur = Vec2(), Vec2(1, 1), 0.0, 0.0, 0.0
        pivot = center
        match kind:
            case "scatter_out":
                offset = travel * (1 - (1 - p) ** 2)
                rotation, scale = spin * p, Vec2(1, 1) * (1 - 0.4 * p)
                opacity = (1 - p) ** 2
            case "converge_out":
                # Resolve body-node centers through layout, rather than character index widths.
                character = next(
                    (
                        c
                        for c in context.line.layout.body.characters
                        if c.object.id == target.node_id
                    ),
                    None,
                )
                x = character.bounds.center if character is not None else None
                distance = -spread * context.line.layout.body.bounds.width / 2
                if x is not None:
                    distance = context.line.layout.body.bounds.center - x
                offset = Vec2(distance * q, 0)
                scale = Vec2(1, 1) * (1 - 0.2 * q)
            case "char_drip" | "spin_flip":
                visible = p if entering else 1 - p
                slope = (
                    tan(min(radians(89), (1 - visible) * pi / 2)) if visible else 0.0
                )
                shear = slope if entering else -slope
                if kind == "spin_flip":
                    shear = -shear
                    scale = Vec2(1, 1) * visible
                    opacity = visible
                else:
                    opacity = float(visible > 0)
                    baseline = target.baseline if target.baseline is not None else center.y * 2
                    pivot = Vec2(center.x * 2, baseline if entering else baseline - center.y * 2)
            case "utopia":
                if entering:
                    pivot = Vec2(0, target.baseline) if target.baseline is not None else center
                    factor = 1.3 * p / 0.8 if p < 0.8 else 1 + 0.3 * (1 - p) / 0.2
                    opacity = min(1, p / 0.8)
                    scale = Vec2(1, 1) * factor
                else:
                    horizontal = sin(pi * p) if p <= 0.5 else 1 + sin(pi * (p - 0.5))
                    offset = Vec2(-horizontal, sin(pi * p / 2)) * (
                        context.line.layout.script_height / 15
                    )
                    opacity = 1 - p
                    scale = Vec2((1 - p) * cos(pi * p), 1 - p)
                    rotation = -180 * p
            case "stretch_in" | "stretch_out":
                scale, blur = Vec2(1 + 2.2 * remaining, 1), em * 0.1 * remaining
            case "glow_in" | "glow_out":
                scale = Vec2(1 + 0.6 * remaining, 1)
                opacity = min(1, 3 * p) if entering else 1 - q
            case "assemble_in":
                opacity = max(0, (q - 0.45) / 0.55)
            case "dissolve_out":
                opacity = 1 - smooth_rate(min(1, p / 0.55))
        transformed = Transform(
            offset=offset, scale=scale, rotation=rotation, opacity=opacity, pivot=pivot
        ).sample(base, p)
        if shear:
            old = transformed.transform.apply(pivot)
            transformed = replace(transformed, skew=transformed.skew + Vec2(0, shear))
            transformed = replace(
                transformed,
                position=transformed.position
                + old
                - transformed.transform.apply(pivot),
            )
        return replace(transformed, blur=base.blur + blur)

    channels: frozenset[Channel] = frozenset(
        {"position", "scale", "rotation", "skew", "opacity"}
    )
    if kind in {"stretch_in", "stretch_out", "glow_in", "glow_out"}:
        channels = frozenset((*channels, "blur"))
    return StateFunction(sample, channels)
