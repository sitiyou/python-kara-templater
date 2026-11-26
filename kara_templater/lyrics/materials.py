"""GPU material functions specific to prepared karaoke timing."""

from dataclasses import dataclass

from ..composition import Color
from ..geometry import Vec2
from ..paint_fields import (
    MaterialClip,
    MaterialEffect,
    PaintInput,
    PaintValue,
    _PaintTrack,
)


@dataclass(frozen=True)
class _GlowMix(MaterialEffect):
    front: _PaintTrack
    axis: Vec2
    origin: float
    sigma: float
    before: Color
    after: Color
    alphas: Vec2

    # Gaussian step response for the color transition. Coverage is supplied
    # by the already blurred silhouette. Color is mixed in premultiplied form.
    wgsl = """
fn shade(ink: vec4<f32>, ctx: KaraPaintContext, front: f32, axis: vec2<f32>,
         origin: f32, sigma: f32, before: vec3<f32>, after: vec3<f32>, alphas: vec2<f32>) -> vec4<f32> {
    let distance = (front - dot(ctx.local, axis) + origin) / sigma;
    let x = abs(distance) * 0.7071067812;
    let t = 1.0 / (1.0 + 0.3275911 * x);
    let error = 1.0 - (((((1.061405429 * t - 1.453152027) * t)
                         + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * exp(-x * x);
    let weight = 0.5 + 0.5 * sign(distance) * error;
    let a = (1.0 - weight) * alphas.x;
    let b = weight * alphas.y;
    return vec4<f32>((before * a + after * b) / max(a + b, 0.000001), ink.a * (a + b));
}
"""

    def _arguments(self) -> tuple[PaintValue | _PaintTrack, ...]:
        return self.front, self.axis, self.origin, self.sigma, self.before, self.after, self.alphas


def _solid_glow(effects: tuple[MaterialClip, ...]) -> bool:
    return any(isinstance(clip.effect, _GlowMix) for clip in effects)


class _SweepBlend(MaterialEffect):
    """Mix two sampled materials at the projected edge of a sweep."""

    wgsl = """
fn shade(ink: vec4<f32>, ctx: KaraPaintContext, waiting: vec3<f32>,
         phase: f32, front: vec3<f32>, has_front: f32) -> vec4<f32> {
    let base = mix(waiting, ink.rgb, smoothstep(0.0, 1.0, phase));
    let glow = smoothstep(0.0, 0.16, phase) * (1.0 - smoothstep(0.42, 0.78, phase));
    return vec4<f32>(mix(base, front, glow * has_front), ink.a);
}
"""


@dataclass(frozen=True)
class _ScanlineTint(MaterialEffect):
    front: _PaintTrack
    inverse_scale: _PaintTrack
    axis: Vec2
    origin: float
    color: Color | PaintInput
    width: float | PaintInput
    softness: float | PaintInput
    rows: Vec2
    strength: float | PaintInput
    overlay: float

    wgsl = """
fn shade(ink: vec4<f32>, ctx: KaraPaintContext, front: f32, inverse_scale: f32,
         axis: vec2<f32>, origin: f32, color: vec3<f32>, width: f32,
         softness: f32, rows: vec2<f32>, strength: f32, overlay: f32) -> vec4<f32> {
    var weight = 0.0;
    let distance = abs(dot(ctx.local, axis) - origin - front);
    let half_width = width * 0.5;
    let room = half_width * inverse_scale - distance;
    if ctx.component <= 1 && ctx.local.y >= rows.x && ctx.local.y < rows.y && room > 0.0 {
        let transition = min(softness, half_width) * inverse_scale;
        weight = strength * smoothstep(0.0, max(transition, 0.000001), room);
    }
    if overlay > 0.0 { return vec4<f32>(color, ink.a * weight); }
    return vec4<f32>(mix(ink.rgb, color, weight), ink.a);
}
"""

    def _arguments(self) -> tuple[PaintValue | PaintInput | _PaintTrack, ...]:
        return (
            self.front, self.inverse_scale, self.axis, self.origin, self.color,
            self.width, self.softness, self.rows, self.strength, self.overlay,
        )
