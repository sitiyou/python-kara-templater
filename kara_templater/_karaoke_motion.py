"""Studio-style motion expressed through the existing StateAnimation protocol."""

from collections.abc import Callable
from dataclasses import dataclass, replace
from math import cos, pi, sin

from .geometry import Vec2
from .lyric_line import LyricAnimationContext
from .particles import ParticleContext
from .scene_animation import (
    Channel,
    StateAnimation,
    StateFunction,
    Transform,
    VisualState,
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
    if kind in {"fade", "char_fade"}:
        return Slide(Vec2(), entering, fast_reveal=False)
    if kind in {"slide_in", "slide_out"}:
        return Slide(Vec2(-em if entering else em, 0), entering)
    if kind in {"rise", "wave_in"}:
        return Slide(Vec2(0, em * 0.55 if entering else -em * 0.55), entering)
    if kind == "tracking_in":
        return Slide(Vec2(spread * em * 1.6, 0), entering)
    random = ParticleContext(target.id, 0, seed, Vec2(), context.line.origin)
    angle = random.uniform("direction", 0, 2 * pi)
    travel = Vec2(cos(angle), sin(angle)) * em * random.uniform("distance", 1.4, 2.6)
    spin = random.uniform("spin", -210, 210)

    def sample(base: VisualState, p: float) -> VisualState:
        q = smooth_rate(p)
        remaining = 1 - q if entering else q
        opacity = min(1, p * 4) if entering else 1 - q
        offset, scale, rotation, shear, blur = Vec2(), Vec2(1, 1), 0.0, 0.0, 0.0
        pivot = center
        match kind:
            case "scatter_out":
                offset = travel * (1 - (1 - p) ** 2)
                rotation, scale = spin * p, Vec2(1, 1) * (1 - 0.45 * q)
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
                scale = Vec2(1, 1) * (1 - 0.65 * q)
            case "char_drip":
                shear = (1 if entering else -1) * 2.4 * remaining
                pivot = Vec2(center.x * 2, center.y * (2 if entering else 0))
            case "spin_flip":
                scale = Vec2(1, 1) * max(0.001, 1 - remaining)
                shear = (1 if entering else -1) * 1.8 * remaining
            case "utopia":
                if entering:
                    factor = (
                        1.12 * smooth_rate(p / 0.6)
                        if p < 0.6
                        else 1 + 0.12 * (1 - smooth_rate((p - 0.6) / 0.4))
                    )
                    scale = Vec2(1, 1) * max(0.001, factor)
                else:
                    offset = Vec2(-em * 1.5 * sin(pi * p / 2), em * sin(pi * p / 2))
                    scale = Vec2((1 - q) * cos(pi * p), 1 - q)
                    rotation = -180 * p
            case "stretch_in" | "stretch_out":
                scale, blur = Vec2(1 + 2.2 * remaining, 1), em * 0.1 * remaining
            case "glow_in" | "glow_out":
                scale, blur = Vec2(1 + 0.6 * remaining, 1), em * 0.14 * remaining
            case "assemble_in":
                opacity = smooth_rate(max(0, (p - 0.45) / 0.55))
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
