"""Studio-style motion expressed through the existing StateAnimation protocol."""

from dataclasses import dataclass, replace
from math import cos, pi, pow, radians, sin, tan

from .easing import ease_out
from .geometry import Vec2
from .lyric_line import LyricAnimationContext, LyricTarget, _line_x
from .scene_animation import (
    Channel,
    FadeIn,
    FadeOut,
    ShaderMotion,
    Slide,
    StateAnimation,
    Transform,
    VisualState,
    smooth_rate,
)
from .scene_evaluation import compose_states

HALO_STROKES = (
    (0.10, 0.42),
    (0.22, 0.24),
    (0.38, 0.14),
    (0.58, 0.08),
    (0.82, 0.045),
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


@dataclass(frozen=True)
class ZoomScale:
    """Note attack followed by Studio's fixed 0.30 second release."""

    note: float
    duration: float
    exponent: int

    def __call__(self, progress: float) -> float:
        elapsed = progress * self.duration
        distance = (
            1 - min(1, elapsed / self.note)
            if elapsed <= self.note
            else min(1, (elapsed - self.note) / 0.30)
        )
        return 1 + 0.10 * (1 - pow(distance, self.exponent))


def zoom_pulse(note: float, duration: float, level: int, pivot: Vec2) -> Transform:
    """Grow during the highlight step and release over 0.30 seconds if still visible."""
    return Transform(scale=ZoomScale(note, duration, max(1, level)), pivot=pivot)


def glow_scale(q: float, entering: bool) -> Vec2:
    return Vec2(1 + 0.6 * (1 - q if entering else q), 1)


def stretch(entering: bool, pivot: Vec2) -> ShaderMotion:
    motion = Transform(
        scale=lambda p: Vec2(
            1 + 2.2 * (1 - smooth_rate(p) if entering else smooth_rate(p)), 1
        ),
        opacity=lambda p: min(1, 4 * p) if entering else 1 - smooth_rate(p),
        pivot=pivot,
    )
    return ShaderMotion(
        motion.sample,
        motion.channels,
        """
        bool entering=item(data+2)>0.;
        float q=smoothstep(0.,1.,p);
        mat2 before=basisOf(scale,skew,angle);
        scale.x*=1.+2.2*(entering?1.-q:q);
        pos+=(before-basisOf(scale,skew,angle))*pairAt(data);
        alpha*=entering?min(1.,4.*p):1.-q;
    """,
        (pivot.x, pivot.y, float(entering)),
    )


def transition(
    context: LyricAnimationContext,
    kind: str,
    entering: bool,
    seed: int,
    zoom_pivot: bool = False,
    glyph_pivot: bool = False,
    host: LyricTarget | None = None,
    reading_edges: tuple[float, float] | None = None,
) -> StateAnimation:
    target = host or context.target
    center = context.target.center
    if reading_edges is not None and kind not in {"utopia", "tilt_pop"}:
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
            glyph = (
                tuple(g for r in context.line.layout.ruby for g in r.layout.characters)[
                    index
                ]
                if target.role == "ruby"
                else context.line.layout.body.characters[index]
            )
            _, drip_edge = _line_x(glyph, glyph.bounds.left, glyph.bounds.right)

    utopia_pivot = center if zoom_pivot or glyph_pivot else target._baseline_pivot
    converge_distance = 0.0
    if kind == "converge_out":
        body = context.line.layout.body
        converge_distance = (
            -spread * em * len(targets) / 2
            if context.target.role == "ruby"
            else body.bounds.center - body.characters[index].bounds.center
        )

    exit_travel = context.line.layout.script_height / 15

    def sample(base: VisualState, p: float) -> VisualState:
        if p == 1 and entering and kind in {"tilt_pop", "utopia"}:
            return base
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
            case "utopia" | "tilt_pop":
                pivot = utopia_pivot
                if entering:
                    factor = 1.3 * p / 0.8 if p < 0.8 else 1 + 0.3 * (1 - p) / 0.2
                    opacity = min(1, p / 0.8)
                    scale = Vec2(1, 1) * factor
                else:
                    horizontal = sin(pi * p) if p <= 0.5 else 1 + sin(pi * (p - 0.5))
                    offset = Vec2(-horizontal, sin(pi * p / 2)) * exit_travel
                    opacity = 1 - p
                    scale = Vec2((1 - p) * cos(pi * p), 1 - p)
                    rotation = -180 * p
                    if not (zoom_pivot or glyph_pivot):
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
        if kind == "tilt_pop":
            angle = -19 * (1 - p) ** 2 + 4 * sin(pi * p)
            transformed = Transform(rotation=angle, pivot=center).sample(transformed, p)
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

    channels: frozenset[Channel] = frozenset(
        {"position", "scale", "rotation", "skew", "opacity"}
    )
    if kind == "tilt_pop" and entering:
        return ShaderMotion(
            sample,
            channels,
            _TILT_POP,
            (center.x, center.y, utopia_pivot.x, utopia_pivot.y),
        )
    if kind == "spin_flip":
        return ShaderMotion(
            sample, channels, _SPIN_FLIP, (center.x, center.y, float(entering))
        )
    parameters: tuple[float, ...] = (center.x, center.y)
    if kind == "char_drip":
        body = """
            float v=entering?p:1.-p;
            skew.y += v>0. ? (entering?1.:-1.)*tan(min(radians(89.),(1.-v)*1.57079633)) : 0.;
            alpha *= float(v>0.);
        """
        parameters = (drip_edge, 0.0)
    elif kind == "scatter_out":
        body = """
            offset=pairAt(data+3)*(1.-(1.-p)*(1.-p));
            angle+=item(data+5)*p; scale*=1.-0.4*p; alpha*=(1.-p)*(1.-p);
        """
        parameters += (float(entering), travel.x, travel.y, spin)
    elif kind == "converge_out":
        body = "offset.x=item(data+3)*q; scale*=1.-0.2*q; alpha*=opacity;"
        parameters += (float(entering), converge_distance)
    elif kind in {"utopia", "tilt_pop"} and not entering:
        body = """
            float h=p<=0.5 ? sin(3.14159265*p) : 1.+sin(3.14159265*(p-0.5));
            offset=vec2(-h,sin(1.57079633*p))*item(data+3);
            scale*=vec2((1.-p)*cos(3.14159265*p),1.-p);
            alpha*=1.-p;
            if(item(data+4)>0.) angle-=180.*p;
            else {
                mat2 outer=basisOf(scale,skew,angle);
                pos+=(before-outer)*pivot+offset;
                vec2 center=pairAt(data+5);
                mat2 rot=basisOf(vec2(1.),vec2(0.),-180.*p);
                pos+=outer*(center-rot*center);
                mat2 m=outer*rot;
                float sx=length(m[0]);
                vec2 axis=sx>0. ? m[0]/sx : vec2(1.,0.);
                scale=vec2(sx,dot(vec2(-axis.y,axis.x),m[1]));
                skew=vec2(sx>0. ? dot(axis,m[1])/sx : 0.,0.);
                angle=degrees(atan(axis.y,axis.x));
                before=basisOf(scale,skew,angle);
                offset=vec2(0.);
            }
        """
        parameters = (
            utopia_pivot.x,
            utopia_pivot.y,
            0.0,
            exit_travel,
            float(zoom_pivot or glyph_pivot),
            center.x,
            center.y,
        )
    elif kind == "utopia":
        parameters = (utopia_pivot.x, utopia_pivot.y)
        body = "scale*=p<0.8 ? 1.3*p/0.8 : 1.+0.3*(1.-p)/0.2; alpha*=min(1.,p/0.8);"
    elif kind in {"glow_in", "glow_out"}:
        body = "scale.x*=1.+0.6*(entering?1.-q:q); alpha*=entering?min(1.,3.*p):1.-q;"
    elif kind == "assemble_in":
        body = "alpha*=max(0.,(q-0.45)/0.55);"
    elif kind == "dissolve_out":
        body = "alpha*=1.-smoothstep(0.,0.55,p);"
    else:
        body = "alpha*=opacity;"
    if len(parameters) == 2:
        parameters += (float(entering),)
    return ShaderMotion(
        sample,
        channels,
        """
        vec2 pivot=pairAt(data), offset=vec2(0.);
        bool entering=item(data+2)>0.;
        float q=smoothstep(0.,1.,p), opacity=entering ? min(1.,4.*p) : 1.-q;
        mat2 before=basisOf(scale,skew,angle);
    """
        + body
        + "pos+=(before-basisOf(scale,skew,angle))*pivot+offset;",
        parameters,
    )


_TILT_POP = """
    vec2 center=pairAt(data), pivot=pairAt(data+2);
    mat2 before=basisOf(scale,skew,angle);
    scale *= p<0.8 ? 1.3*p/0.8 : 1.+0.3*(1.-p)/0.2;
    mat2 scaled=basisOf(scale,skew,angle);
    pos += (before-scaled)*pivot;
    angle += -19.*(1.-p)*(1.-p)+4.*sin(3.14159265*p);
    pos += (scaled-basisOf(scale,skew,angle))*center;
    alpha *= min(1.,p/0.8);
"""

_SPIN_FLIP = """
    vec2 pivot=pairAt(data);
    mat2 before=basisOf(scale,skew,angle);
    bool entering=item(data+2)>0.;
    float v=entering ? p : 1.-p;
    scale *= v;
    if(v>0.) skew.y += (entering ? -1. : 1.)*tan(min(radians(89.),(1.-v)*1.57079633));
    pos += (before-basisOf(scale,skew,angle))*pivot;
    alpha *= v;
"""
