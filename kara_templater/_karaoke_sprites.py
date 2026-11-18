"""Original vector ornaments and deterministic trajectories for built-in karaoke."""

from functools import lru_cache
from math import cos, pi, sin, sqrt

from .composition import Color
from .easing import ease_out
from .geometry import Contour, CubicSegment, Vec2, VectorPath
from .karaoke_cues import _note
from .particles import ParticleContext
from .scene import Lifetime, PathObject
from .scene_animation import Transform, VisualState, smooth_rate


@lru_cache(maxsize=16)
def sprite(kind: str) -> VectorPath:
    if kind in {"sparkle", "twinkle", "twinkle_classic"}:
        tip = Vec2(0, -0.5)
        control = Vec2(0.055, -0.055)
        corner = Vec2(0.5, 0)
        arc = CubicSegment(
            tip.lerp(control, 2 / 3), corner.lerp(control, 2 / 3), corner
        )
        segments = tuple(
            CubicSegment(
                arc.control1.rotated(a), arc.control2.rotated(a), arc.end.rotated(a)
            )
            for a in range(0, 360, 90)
        )
        return VectorPath((Contour(tip, segments),))
    if kind == "ripple":
        outer, inner = VectorPath.circle(0.490), VectorPath.circle(0.462)
        # Opposite winding preserves a transparent hole in both ASS and GPU coverage.
        return VectorPath(
            (*outer.contours, *inner.map(lambda p: Vec2(-p.x, p.y)).contours)
        )
    if kind == "note":
        return _note("note8", 1).map(lambda p: p - Vec2(0.5, 0.5))
    if kind == "petal":
        return VectorPath(
            (
                Contour(
                    Vec2(0, 0.37),
                    (
                        CubicSegment(
                            Vec2(-0.11, 0.28), Vec2(-0.28, 0.02), Vec2(-0.23, -0.20)
                        ),
                        CubicSegment(
                            Vec2(-0.20, -0.37), Vec2(-0.09, -0.35), Vec2(0, -0.26)
                        ),
                        CubicSegment(
                            Vec2(0.09, -0.35), Vec2(0.20, -0.37), Vec2(0.23, -0.20)
                        ),
                        CubicSegment(Vec2(0.28, 0.02), Vec2(0.11, 0.28), Vec2(0, 0.37)),
                    ),
                ),
            )
        )
    if kind in {"snow", "snow_solid"}:
        # Six symmetric branches, with a small central hexagonal opening in lace mode.
        contours = []
        for branch in range(6):
            angle = branch * pi / 3
            pts = (
                Vec2(0.18, -0.055),
                Vec2(0.59, -0.055),
                Vec2(0.4, -0.24),
                Vec2(0.47, -0.30),
                Vec2(0.70, -0.07),
                Vec2(1, -0.055),
                Vec2(1, 0.055),
                Vec2(0.70, 0.07),
                Vec2(0.47, 0.30),
                Vec2(0.4, 0.24),
                Vec2(0.59, 0.055),
                Vec2(0.18, 0.055),
            )
            contours.extend(
                VectorPath.polygon(
                    *(
                        Vec2(
                            p.x * cos(angle) - p.y * sin(angle),
                            p.x * sin(angle) + p.y * cos(angle),
                        )
                        for p in pts
                    )
                ).contours
            )
        if kind == "snow_solid":
            contours.extend(VectorPath.circle(0.24).contours)
        return VectorPath(tuple(contours)).map(lambda p: p * 0.5)
    return VectorPath.polygon(
        Vec2(-0.6, -0.6), Vec2(0.6, -0.6), Vec2(0.6, 0.6), Vec2(-0.6, 0.6)
    )


def _falling_motion(
    context: ParticleContext,
    box: Vec2,
    size: float,
    *,
    snow: bool,
    entering: bool,
    exiting: bool,
) -> Transform:
    """Studio's three falling paths share endpoints, sideways sway and spin."""
    x, phase, angle, depth, drift = (
        context.uniform(key) for key in ("x", "phase", "angle", "depth", "drift")
    )
    start_x = end_x = (x - 0.5) * (0.85 if entering or exiting else 0.7)
    if snow:
        start_y = -0.68 - 0.22 * phase
        if entering:
            start_x += (drift - 0.5) * 0.6
            end_y = 0.35 + 0.2 * depth
        elif exiting:
            start_x += (drift - 0.5) * 0.5
            end_x += 0.35 + 0.6 * drift
            end_y = 0.45 + 0.3 * phase
        else:
            end_y = (depth - 0.5) * 0.6
    elif entering:
        start_x += (drift - 0.5) * 0.7
        start_y, end_y = -0.6 - 0.3 * phase, (depth - 0.5) * 0.55
    else:
        start_y = (depth - 0.5) * 0.55 if exiting else -0.25 - 0.3 * depth
        end_y = start_y + (0.55 if exiting else 0.4) + 0.3 * phase
        if exiting:
            end_x += 0.5 + 0.9 * drift
    start, end = (
        Vec2(start_x * box.x, start_y * box.y),
        Vec2(end_x * box.x, end_y * box.y),
    )
    cycles = 0.35 + 0.45 * drift if snow else 0.9 + 0.9 * drift
    swing = size * (0.75 + 0.65 * depth if snow else 0.8 + 0.7 * depth)
    spin = (80 + 140 * drift if snow else 160 + 240 * drift) * (
        1 if depth >= 0.5 else -1
    )

    def position(p: float) -> Vec2:
        q = p if snow else ease_out(p) if entering else smooth_rate(p)
        return start.lerp(end, q) + Vec2(swing * sin(2 * pi * (phase + cycles * p)), 0)

    def scale(p: float) -> float:
        if snow:
            return size * (0.70 + 0.50 * depth) * (1.05 - 0.40 * p)
        return (
            size
            * (0.72 + 0.55 * depth)
            * (1 - 0.10 * p if exiting else 0.85 + 0.15 * sin(pi * p))
        )

    def opacity(p: float) -> float:
        if exiting:
            return (1 - p) * (1 - 0.5 * p)
        fade_in = min(1, p * (4 if snow else 5))
        return fade_in * ((1 - p) * (1 - 0.4 * p) if entering else sin(pi * p))

    return Transform(
        offset=position,
        scale=scale,
        rotation=lambda p: 360 * angle + spin * p,
        opacity=opacity,
    )


def ornament(
    context: ParticleContext,
    kind: str,
    *,
    size: float,
    box: Vec2,
    duration: float,
    color: Color,
    entering: bool = False,
    exiting: bool = False,
) -> PathObject:
    random = context.uniform
    wind = random("wind", -0.7, 0.7)
    turn = random("turn", -90, 90)
    amplitude = size * random("amplitude", 0.65, 1.35)
    phase = random("phase")
    rise = random("rise")
    shrink = random("shrink", 0.55, 0.85)

    def offset(p: float) -> Vec2:
        if kind == "twinkle_classic" or kind == "ripple":
            return Vec2()
        if kind == "note":
            return Vec2(
                size * 0.4 * sin(2 * pi * (phase + 1.5 * p)), -size * 1.8 * ease_out(p)
            )
        if kind in {"twinkle", "sparkle"}:
            travel = size * (3.2 if entering or exiting else 1.8)
            return Vec2(wind * 0.25, -0.45 * (0.3 + 0.7 * rise)) * (travel * p)
        if kind == "assemble":
            return Vec2(wind * size * 24, -size * 18) * (1 - smooth_rate(p))
        if kind == "dissolve":
            return Vec2(wind * size * 24, -size * (8 + 14 * rise)) * smooth_rate(
                p
            )
        return Vec2(
            wind * size * p * 3,
            -size * (3 if kind == "note" else 2) * (1 - (1 - p) ** 2),
        )

    def scale(p: float) -> Vec2:
        if kind == "ripple":
            return Vec2(1, 1) * size * 3.6 * (0.25 + 0.85 * (1 - (1 - p) ** 2))
        if kind == "note":
            return Vec2(1, 1) * amplitude * (0.85 + 0.15 * sin(pi * p))
        if kind in {"sparkle", "twinkle"}:
            return Vec2(1, 1) * amplitude * (1 - p * shrink)
        value = (
            amplitude * (0.35 + 0.65 * sin(pi * p))
            if kind == "twinkle_classic"
            else amplitude * (1 - 0.4 * p)
        )
        return Vec2(value, value)

    def opacity(p: float) -> float:
        if kind == "note":
            return 1 - p * sqrt(p)
        if kind in {"sparkle", "twinkle"}:
            return 1 - p
        if kind == "ripple":
            return (1 - p) ** 2
        if kind == "twinkle_classic":
            return max(0, sin(pi * p))
        return min(1, p * 8) * (1 - smooth_rate(p))

    falling = kind in {"petal", "snow", "snow_solid"}
    if kind in {"twinkle_classic", "note", "ripple"}:
        turn = 0
    elif kind in {"twinkle", "sparkle"}:
        turn = 60
    motion = (
        _falling_motion(
            context, box, size, snow=kind != "petal", entering=entering, exiting=exiting
        )
        if falling
        else Transform(
            offset=offset, scale=scale, opacity=opacity, rotation=lambda p: turn * p
        )
    )
    return PathObject(
        id=context.id,
        origin=context.origin,
        lifetime=Lifetime(context.birth, context.birth + duration),
        path=sprite(kind),
        layer=2,
        state=VisualState(
            position=context.position,
            fill=color,
            outline=color,
            blur=0,
            rotation=0 if falling else random("angle", -30, 30),
        ),
    ).animate(motion, duration=duration)
