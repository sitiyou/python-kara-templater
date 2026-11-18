"""Original vector ornaments and deterministic trajectories for built-in karaoke."""

from math import cos, pi, sin

from .composition import Color
from .geometry import Contour, CubicSegment, Vec2, VectorPath
from .particles import ParticleContext
from .scene import Lifetime, PathObject
from .scene_animation import Transform, VisualState, smooth_rate


def sprite(kind: str) -> VectorPath:
    if kind in {"sparkle", "twinkle", "twinkle_classic"}:
        return VectorPath.polygon(
            *(
                Vec2(cos(i * pi / 4), sin(i * pi / 4)) * (1 if i % 2 == 0 else 0.17)
                for i in range(8)
            )
        )
    if kind == "ripple":
        outer, inner = VectorPath.circle(1), VectorPath.circle(0.94)
        # Opposite winding preserves a transparent hole in both ASS and GPU coverage.
        return VectorPath(
            (*outer.contours, *inner.map(lambda p: Vec2(-p.x, p.y)).contours)
        )
    if kind == "note":
        return VectorPath(
            (
                Contour(
                    Vec2(-0.7, 0.5),
                    (
                        CubicSegment(Vec2(-1.1, 0.1), Vec2(0.1, -0.1), Vec2(0.1, 0.4)),
                        CubicSegment(Vec2(0.1, 0.9), Vec2(-0.8, 1), Vec2(-0.7, 0.5)),
                    ),
                ),
                *VectorPath.polygon(
                    Vec2(-0.02, 0.4), Vec2(-0.02, -1), Vec2(0.15, -1), Vec2(0.15, 0.4)
                ).contours,
                Contour(
                    Vec2(0.15, -1),
                    (
                        CubicSegment(
                            Vec2(0.9, -0.85), Vec2(0.95, -0.3), Vec2(0.35, -0.25)
                        ),
                        CubicSegment(
                            Vec2(0.65, -0.6), Vec2(0.3, -0.55), Vec2(0.15, -0.75)
                        ),
                    ),
                ),
            )
        )
    if kind == "petal":
        return VectorPath(
            (
                Contour(
                    Vec2(0, -0.7),
                    (
                        CubicSegment(Vec2(-1.4, -0.8), Vec2(-0.9, 0.9), Vec2(0, 1)),
                        CubicSegment(Vec2(0.9, 0.9), Vec2(1.4, -0.8), Vec2(0, -0.7)),
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
        return VectorPath(tuple(contours))
    return VectorPath.polygon(
        Vec2(-0.6, -0.6), Vec2(0.6, -0.6), Vec2(0.6, 0.6), Vec2(-0.6, 0.6)
    )


def ornament(
    context: ParticleContext,
    kind: str,
    *,
    size: float,
    duration: float,
    color: Color,
    entering: bool = False,
    exiting: bool = False,
) -> PathObject:
    random = context.uniform
    wind = random("wind", -0.7, 0.7)
    turn = random("turn", -90, 90)
    phase = random("phase", 0, 2 * pi)
    amplitude = size * random("amplitude", 0.75, 1.25)

    def offset(p: float) -> Vec2:
        if kind == "twinkle_classic" or kind == "ripple":
            return Vec2()
        if kind in {"petal", "snow", "snow_solid"}:
            q = smooth_rate(p)
            return Vec2(
                size * (wind * p * 3 + 0.8 * (sin(phase + pi * p) - sin(phase))),
                size * 3 * (q - (1 if entering else 0)),
            )
        if kind == "assemble":
            return Vec2(wind * size * 24, -size * 18) * (1 - smooth_rate(p))
        if kind == "dissolve":
            return Vec2(wind * size * 24, -size * random("rise", 8, 22)) * smooth_rate(
                p
            )
        return Vec2(
            wind * size * p * 3,
            -size * (3 if kind == "note" else 2) * (1 - (1 - p) ** 2),
        )

    def scale(p: float) -> Vec2:
        if kind == "ripple":
            return Vec2(1, 1) * amplitude * (0.15 + 2.8 * (1 - (1 - p) ** 2))
        value = (
            amplitude * (0.35 + 0.65 * sin(pi * p))
            if kind == "twinkle_classic"
            else amplitude * (1 - 0.4 * p)
        )
        return Vec2(
            value * (0.18 + 0.82 * abs(cos(phase + 2 * pi * p)))
            if kind == "petal"
            else value,
            value,
        )

    def opacity(p: float) -> float:
        if kind == "twinkle_classic":
            return max(0, sin(pi * p))
        return min(1, p * 8) * (1 - smooth_rate(p))

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
            blur=0.45 if kind in {"twinkle", "sparkle"} else 0.15,
            rotation=random("angle", -30, 30),
        ),
    ).animate(
        Transform(
            offset=offset, scale=scale, opacity=opacity, rotation=lambda p: turn * p
        ),
        duration=duration,
    )
