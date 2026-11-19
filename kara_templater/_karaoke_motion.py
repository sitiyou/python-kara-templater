"""Studio-style motion expressed through the existing StateAnimation protocol."""

from collections.abc import Callable
from dataclasses import dataclass, replace
from math import cos, pi, pow, radians, sin, tan

from .easing import ease_out
from .geometry import Vec2
from .lyric_line import LyricAnimationContext, LyricTarget, _line_x
from .scene_animation import (
    Channel,
    FadeIn,
    FadeOut,
    StateAnimation,
    StateFunction,
    Transform,
    VisualState,
    smooth_rate,
)
from .scene_evaluation import compose_states


@dataclass(frozen=True)
class Slide:
    """Studio translation keeps its short entry reveal on a separate curve."""

    offset: Vec2
    entering: bool
    fast_reveal: bool = True
    rate: Callable[[float], float] = smooth_rate

    @property
    def channels(self) -> frozenset[Channel]:
        return frozenset(("position", "opacity"))

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


class RowSlide(Slide):
    """First-row lyrics slide to the left, subsequent rows to the right."""

    def for_row(self, row: int | None) -> Slide:
        return replace(self, offset=Vec2(-self.offset.x, 0)) if row else self


def unit_hash(index: int, channel: int) -> float:
    """Studio's deterministic 24-bit sample, using unsigned 32-bit arithmetic."""
    value = (index * 0x85EBCA77 + channel * 0xC2B2AE3D) & 0xFFFFFFFF
    value = ((value ^ (value >> 15)) * 0x2545F491) & 0xFFFFFFFF
    return ((value ^ (value >> 13)) & 0xFFFFFF) / 0x1000000


def _scatter(index: int, seed: int, em: float) -> tuple[Vec2, float]:
    seed += index
    angle = 2 * pi * unit_hash(seed, 1)
    travel = em * 2.2 * (0.55 + 0.45 * unit_hash(seed, 2))
    return Vec2(cos(angle), sin(angle)) * travel, (unit_hash(seed, 3) - 0.5) * 720


def zoom_pulse(note: float, duration: float, level: int, pivot: Vec2) -> Transform:
    """Grow during the sung step and release over 0.30 seconds if still visible."""
    exponent = max(1, level)

    def scale(progress: float) -> float:
        t = progress * duration
        if t <= note:
            return 1.25 - 0.25 * pow(1 - min(1, t / note), exponent)
        return 1.25 - 0.25 * pow(min(1, (t - note) / 0.30), exponent)

    return Transform(scale=scale, pivot=pivot)


def glow_scale(q: float, entering: bool) -> Vec2:
    return Vec2(1 + 0.6 * (1 - q if entering else q), 1)


def stretch(entering: bool, pivot: Vec2) -> Transform:
    return Transform(
        scale=lambda p: Vec2(
            1 + 2.2 * (1 - smooth_rate(p) if entering else smooth_rate(p)), 1
        ),
        opacity=lambda p: min(1, 4 * p) if entering else 1 - smooth_rate(p),
        pivot=pivot,
    )


def transition(
    context: LyricAnimationContext,
    kind: str,
    entering: bool,
    seed: int,
    zoom_pivot: bool = False,
    host: LyricTarget | None = None,
    reading_edges: tuple[float, float] | None = None,
) -> StateAnimation:
    target = host or context.target
    center = context.target.center
    if reading_edges is not None and kind != "utopia":
        center = Vec2(sum(reading_edges) / 2, center.y)
    em = target.em_size or max(1, center.y * 2)
    targets = context.line.query(target.role)
    index = targets.index(target)
    spread = 0 if len(targets) < 2 else 2 * index / (len(targets) - 1) - 1
    if kind in {"stretch_in", "stretch_out"}:
        return stretch(entering, center)
    if kind == "char_fade":
        return FadeIn() if entering else FadeOut()
    if kind == "fade":
        return FadeIn(rate=ease_out) if entering else FadeOut(rate=ease_out)
    if kind in {"slide_in", "slide_out"}:
        return RowSlide(
            Vec2(-max(36, 0.9 * em), 0), entering, fast_reveal=False, rate=ease_out
        )
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

    drip_edge = center.x
    if kind == "char_drip":
        if reading_edges is not None:
            drip_edge = reading_edges[1]
        else:
            glyph = context.line.layout.body.characters[index]
            _, drip_edge = _line_x(glyph, glyph.bounds.left, glyph.bounds.right)

    converge_distance = 0.0
    if kind == "converge_out":
        body = context.line.layout.body
        converge_distance = (
            -spread * em * len(targets) / 2 if context.target.role == "ruby"
            else body.bounds.center - body.characters[index].bounds.center
        )

    def sample(base: VisualState, p: float) -> VisualState:
        q = smooth_rate(p)
        opacity = min(1, p * 4) if entering else 1 - q
        offset, scale, rotation, shear = Vec2(), Vec2(1, 1), 0.0, 0.0
        pivot = center
        match kind:
            case "scatter_out":
                offset = travel * (1 - (1 - p) ** 2)
                rotation, scale = spin * p, Vec2(1, 1) * (1 - 0.4 * p)
                opacity = (1 - p) ** 2
            case "converge_out":
                offset = Vec2(converge_distance * q, 0)
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
                    # Vertical shear fixes the entire right edge regardless of pivot y.
                    pivot = Vec2(drip_edge, 0)
            case "utopia":
                pivot = (
                    center
                    if zoom_pivot or target.baseline is None
                    else Vec2(0, target.baseline)
                )
                if entering:
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
                    if not zoom_pivot:
                        # Studio turns around the character centre first, then flips
                        # and shrinks the rotated shape about its left baseline.
                        outer = Transform(
                            offset=offset, scale=scale, opacity=opacity, pivot=pivot
                        ).sample(base, p)
                        inner = Transform(rotation=rotation, pivot=center).sample(
                            VisualState(), p
                        )
                        combined = compose_states(outer, inner)
                        return replace(
                            outer,
                            position=combined.position,
                            rotation=combined.rotation,
                            scale=combined.scale,
                            skew=combined.skew,
                        )
            case "glow_in" | "glow_out":
                scale = glow_scale(q, entering)
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
        return transformed

    return StateFunction(
        sample, frozenset({"position", "scale", "rotation", "skew", "opacity"})
    )
