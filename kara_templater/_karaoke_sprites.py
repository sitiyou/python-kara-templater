"""Original vector ornaments and deterministic trajectories for built-in karaoke."""

from collections.abc import Callable, Iterator
from dataclasses import replace
from functools import lru_cache
from math import ceil, cos, pi, sin, sqrt

from ._karaoke_motion import unit_hash
from .composition import Color, Paint
from .easing import ease_out
from .geometry import Contour, CubicSegment, Vec2, VectorPath
from .karaoke_cues import _note
from .paint_fields import ColorRamp
from .particles import ParticleContext
from .scene import Lifetime, PathObject
from .scene_animation import Channel, StateFunction, Transform, VisualState, smooth_rate


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
    if kind == "snow_solid":
        return VectorPath.polygon(
            *(
                Vec2(0, -radius).rotated(arm + angle)
                for arm in range(0, 360, 60)
                for angle, radius in ((0, 0.47), (20, 0.25), (30, 0.085), (40, 0.25))
            )
        )
    if kind == "snow":
        return _lace_snowflake()
    return VectorPath.polygon(
        Vec2(-0.18, -0.18), Vec2(0.18, -0.18), Vec2(0.18, 0.18), Vec2(-0.18, 0.18)
    )


def _lace_snowflake() -> VectorPath:
    """Build a six-arm dendrite from the perimeter and window of one 60° sector."""

    def reflect(point: Vec2) -> Vec2:
        return Vec2(point.x, -point.y).rotated(60)

    # One side of the arm, walking from the main tip past the two side branches.
    half_arm = (
        Vec2(0.470, 0),
        Vec2(0.418, 0.030),
        Vec2(0.345, 0.030),
        Vec2(0.395, 0.143),
        Vec2(0.315, 0.030),
        Vec2(0.197, 0.030),
    )
    sector = (
        *half_arm,
        Vec2(0.312, 0).rotated(30),
        *(reflect(p) for p in reversed(half_arm[1:])),
    )
    perimeter = VectorPath.polygon(
        *(p.rotated(a) for a in range(0, 360, 60) for p in sector)
    )
    # Reverse winding for the six windows and the central hexagonal opening.
    base, inner_branch = Vec2(0.102, 0.030), Vec2(0.167, 0.030)
    window = (
        base,
        reflect(base),
        reflect(inner_branch),
        Vec2(0.260, 0).rotated(30),
        inner_branch,
    )
    holes = tuple(
        VectorPath.polygon(*(p.rotated(a) for p in window)).contours[0]
        for a in range(0, 360, 60)
    )
    center = VectorPath.polygon(
        *(Vec2(0.0935, 0).rotated(-a) for a in range(0, 360, 60))
    )
    return VectorPath((*perimeter.contours, *holes, *center.contours))


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
    x, phase, angle, depth, drift = (unit_hash(context.seed, c) for c in range(1, 6))
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
    em: float,
    index: int,
    box: Vec2,
    duration: float,
    color: Color,
    radial: ColorRamp | None = None,
    entering: bool = False,
    exiting: bool = False,
    display: Lifetime | None = None,
) -> PathObject | None:
    x, phase, angle, depth = (unit_hash(context.seed, c) for c in range(1, 5))
    rotation = 0.0
    position = context.position
    if kind == "ripple":
        delay = index * 0.15
        motion = Transform(
            scale=lambda p: size * 3.6 * (0.25 + 0.85 * ease_out(p)),
            opacity=lambda p: (1 - p) ** 2,
        )
    elif kind == "note":
        delay = angle * duration * 0.35
        position += Vec2((x - 0.5) * box.x * 0.8, -0.35 * box.y)
        rotation = (phase - 0.5) * 28
        motion = Transform(
            offset=lambda p: (
                Vec2(0.4 * sin(2 * pi * (phase + 1.5 * p)), -1.8 * ease_out(p)) * size
            ),
            scale=lambda p: size * (0.70 + 0.60 * x) * (0.85 + 0.15 * sin(pi * p)),
            opacity=lambda p: 1 - p * sqrt(p),
        )
    elif kind in {"assemble_in", "dissolve_out"}:
        delay = angle * (0.09 if entering else 0.07)
        position += Vec2((x - 0.5) * box.x * 0.9, (depth - 0.5) * box.y * 0.8)
        direction = Vec2(cos(phase * 2 * pi), sin(phase * 2 * pi) * 0.7)
        travel = direction * (2.2 * em * (0.6 + 0.5 * depth))
        spin = (angle - 0.5) * 240
        if entering:
            motion = Transform(
                offset=lambda p: travel * (1 - smooth_rate(p)),
                rotation=lambda p: spin * (1 - smooth_rate(p)),
                scale=lambda p: 0.75 * size * (0.9 - 0.35 * smooth_rate(p)),
                opacity=lambda p: min(1, 6 * p) * (1 - p * p),
            )
        else:
            motion = Transform(
                offset=lambda p: travel * smooth_rate(p),
                rotation=lambda p: spin * smooth_rate(p),
                scale=lambda p: 0.75 * size * (1 - 0.25 * smooth_rate(p)),
                opacity=lambda p: (1 - p) * (1 - 0.5 * p),
            )
    else:
        snow = kind != "petal"
        delay = angle * (0.16 if snow else 0.11)
        motion = _falling_motion(
            context, box, size, snow=snow, entering=entering, exiting=exiting
        )
    if delay >= duration:
        return None
    animation: Transform | StateFunction = motion
    if radial is not None:
        def ring_color(base: VisualState, p: float) -> VisualState:
            ink = radial.at(round(32 * ease_out(p)) / 32)
            return replace(motion.sample(base, p), fill=ink)
        animation = StateFunction(ring_color, motion.channels | frozenset[Channel](("fill",)))
    return _draw(
        replace(context, birth=context.birth + delay, position=position),
        kind,
        duration - delay,
        color,
        animation,
        display,
        angle=rotation, raster_size=size * (4 if kind == "ripple" else 1),
    )


@lru_cache(maxsize=128)
def _sized_sprite(kind: str, pixels: int) -> VectorPath:
    return sprite(kind).map(lambda point: point * pixels)


def _draw(
    context: ParticleContext,
    kind: str,
    duration: float,
    color: Color,
    motion: Transform | StateFunction,
    display: Lifetime | None,
    *,
    raster_size: float,
    angle: float = 0,
) -> PathObject | None:
    start, end = context.birth, context.birth + duration
    animation: Transform | StateFunction = motion
    if display is not None:
        start, end = max(start, display.start), min(end, display.end)
        if end <= start:
            return None
        # The line can open mid-flight. Preserve the original phase at both boundaries.
        phase = (start - context.birth) / duration
        span = (end - start) / duration
        animation = StateFunction(
            lambda base, p: motion.sample(base, min(1, phase + p * span)),
            motion.channels,
        )
    # GPU coverage is cached before motion. Store the contour at its display
    # size so a unit-wide petal or thin ring survives rasterization.
    pixels = max(1, ceil(raster_size))
    return PathObject(
        id=context.id,
        origin=context.origin,
        lifetime=Lifetime(start, end),
        path=_sized_sprite(kind, pixels),
        layer=-1 if kind == "ripple" else 2,
        state=VisualState(
            position=context.position,
            scale=Vec2(1 / pixels, 1 / pixels),
            fill=color,
            outline=color,
            blur=0,
            rotation=angle,
        ),
    ).animate(animation, duration=end - start)


def painted_particle(
    node: PathObject, pen: Paint | None, color_at_x: Callable[[float], Color] | None,
) -> Iterator[PathObject]:
    """Paint the moving face and its independent rim in source order."""
    if pen is not None:
        unit = 1 / node.state.scale.x
        if pen.glow is not None:
            rim = pen.glow
            yield replace(node, id=node.id + "/rim", scale_border=True, state=replace(
                node.state, fill=rim.color, outline=rim.color, border=rim.border * unit,
                opacity=node.state.opacity * rim.opacity,
            ))
        node = replace(node, scale_border=True, state=replace(node.state, outline=pen.outline, border=pen.border * unit))
    if color_at_x is not None:
        clip, = node.animations
        motion = clip.animation
        def tint(base: VisualState, p: float) -> VisualState:
            state = motion.sample(base, p)
            return replace(state, fill=color_at_x(state.position.x))
        animation = StateFunction(tint, motion.channels | frozenset[Channel](("fill",)))
        node = replace(node, animations=(replace(clip, animation=animation),))
    yield node


def star_burst(
    context: ParticleContext,
    kind: str,
    *,
    box: Vec2,
    size: float,
    duration: float,
    count: int,
    colors: tuple[Color, ...],
    pens: tuple[Paint, ...] = (),
    exiting: bool,
    display: Lifetime | None,
    fields: tuple[Callable[[float], Color] | None, ...] = (),
) -> Iterator[PathObject]:
    """Emit one deterministic star pattern per palette colour around the box centre."""
    for variant, color in enumerate(colors):
        previous = None
        for index in range(variant, count, len(colors)):
            seed = context.seed + index // len(colors) + variant * 0x9E37
            x, y, angle, shrink, jitter = (unit_hash(seed, c) for c in range(1, 6))
            if kind == "twinkle_classic":
                lifetime = 0.30 + 0.15 * shrink
                delay = angle * max(0, duration - lifetime) * 0.8
                offset = Vec2((x - 0.5) * box.x * 0.95, (y - 0.5) * box.y * 0.85)
                peak = size * (0.65 + 0.70 * shrink)
                motion = Transform(
                    scale=lambda p, peak=peak: peak * (0.30 + 0.70 * sin(pi * p)),
                    opacity=lambda p: sin(pi * p),
                )
                rotation = angle * 120 - 30
            else:
                # Adjacent stars in the same colour stream must occupy different quadrants.
                left = x < 0.5
                split = 0.62 / 0.92
                if previous == (left, y < split):
                    a, b = unit_hash(seed, 6), unit_hash(seed, 7)
                    y = next(
                        (v for v in (a, b) if (left, v < split) != previous),
                        split + (1 - split) * a if y < split else split * b,
                    )
                previous = (left, y < split)
                offset = Vec2((x - 0.5) * box.x, (0.92 * y - 0.62) * box.y)
                delay = (1 - x if exiting else x) * 0.35 + jitter * 0.09
                lifetime = duration - delay
                travel = size * (3.2 if kind == "sparkle" else 1.8)
                drift = Vec2((shrink - 0.5) * 0.35, -(0.30 + 0.70 * y) * 0.45) * travel
                peak = size * (0.65 + 0.70 * angle)
                motion = Transform(
                    offset=lambda p, d=drift: d * p,
                    scale=lambda p, a=peak, b=shrink: a * (1 - p * (0.85 - 0.30 * b)),
                    rotation=lambda p: 60 * p,
                    opacity=lambda p: 1 - p,
                )
                rotation = angle * 90
            if lifetime <= 0:
                continue
            star = _draw(
                replace(
                    context,
                    id=f"{context.id}:{index}",
                    birth=context.birth + delay,
                    position=context.position + offset,
                ),
                kind,
                lifetime,
                color,
                motion,
                display,
                angle=rotation, raster_size=size,
            )
            if star is not None:
                yield from painted_particle(star, pens[variant] if pens else None, fields[variant] if fields else None)
