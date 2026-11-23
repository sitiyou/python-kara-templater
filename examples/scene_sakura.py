"""E04: seeded sakura particles, birth capture on a lyric cursor, and its echoes.

"""

from dataclasses import replace
from math import cos, sin, tau

from kara_templater import (
    PINK,
    WHITE,
    AnimationClip,
    Contour,
    CubicSegment,
    Document,
    Emission,
    EventOrigin,
    Lifetime,
    Line,
    LineSegment,
    MoveAlong,
    ParticleContext,
    PathObject,
    Scene,
    SoftSweep,
    SourceRef,
    StateFunction,
    Style,
    Vec2,
    VectorPath,
    VisualState,
    echoes,
    emit_particles,
    layout_document_text,
    smooth_rate,
)

PETAL = VectorPath(
    (
        Contour(
            Vec2(0, -8),
            (
                CubicSegment(Vec2(-6, -19), Vec2(-20, -7), Vec2(-3, 14)),
                CubicSegment(Vec2(-1, 18), Vec2(2, 17), Vec2(5, 12)),
                CubicSegment(Vec2(20, -7), Vec2(8, -19), Vec2(2, -12)),
                LineSegment(Vec2(0, -8)),
            ),
        ),
    )
)


def petal(
    context: ParticleContext, *, spread: float = 0, linear: bool = False
) -> PathObject:
    size = context.uniform("size", 0.45, 0.9)
    angle = context.uniform("angle", 0, 360)
    phase = context.uniform("phase", 0, tau)
    position = context.position + Vec2(context.uniform("spread", 0, spread), 0)
    lifetime = Lifetime(context.birth, context.birth + 3)
    if linear:
        path = Contour(
            Vec2(), (LineSegment(Vec2(context.uniform("wind", -100, 100), 900)),), False
        )
    else:
        wind = context.uniform("wind", -170, 170)
        path = Contour(
            Vec2(),
            (
                CubicSegment(
                    Vec2(wind + 140, 90), Vec2(wind - 120, 250), Vec2(wind, 340)
                ),
            ),
            False,
        )
    motion = AnimationClip(
        0, 3, MoveAlong(path) if linear else MoveAlong(path, smooth_rate)
    )
    animations = (motion,)
    if not linear:

        def flutter(state: VisualState, progress: float) -> VisualState:
            return replace(
                state,
                scale=Vec2(
                    size * (0.25 + 0.75 * abs(cos(progress * tau * 2 + phase))), size
                ),
                rotation=angle + progress * 180 + sin(progress * tau * 2 + phase) * 30,
                opacity=min(1, (1 - progress) / 0.25),
            )

        animations += (
            AnimationClip(
                0,
                3,
                StateFunction(flutter, frozenset(("scale", "rotation", "opacity"))),
                breakpoints=(2.25,),
            ),
        )
    return PathObject(
        id=context.id,
        path=PETAL,
        lifetime=lifetime,
        state=VisualState(
            position=position,
            scale=Vec2(size, size),
            rotation=angle,
            fill=PINK,
            outline=WHITE,
            border=0.5,
        ),
        animations=animations,
        layer=-1,
    )


def build() -> Scene:
    document = Document.create(
        styles=(Style(fontname="DejaVu Sans", fontsize=72, outline=1, shadow=0),)
    )
    record_index = len(document.records)
    document.records.append(Line(text=r"{\k100}SAKURA", start_time=1000, end_time=2000))
    layout = layout_document_text(
        document, record_index, id="lyric", display=Lifetime(0, 5)
    )
    origin = Vec2((1280 - layout.bounds.width) / 2, 300)
    front = SoftSweep(
        left=origin.x,
        right=origin.x + layout.bounds.width,
        start=1,
        duration=1,
        fill=(WHITE, PINK),
        outline=(WHITE, PINK),
        width=24,
        outline_width=32,
    )
    lyrics = replace(
        layout.group(position=origin),
        children=tuple(
            replace(item.object, material=front) for item in layout.characters
        ),
    )
    front_start = front.front_at(front.start)
    front_distance = front.front_at(front.start + front.duration) - front_start
    cursor = PathObject(
        id="cursor",
        path=VectorPath.circle(4),
        lifetime=Lifetime(front.start, front.start + front.duration),
        state=VisualState(
            position=Vec2(front_start, origin.y + layout.bounds.height / 2), fill=PINK
        ),
        layer=1,
        animations=(
            AnimationClip(
                0,
                front.duration,
                MoveAlong(
                    Contour(Vec2(), (LineSegment(Vec2(front_distance, 0)),), False),
                    front.rate,
                ),
            ),
        ),
        origin=EventOrigin((SourceRef(layout.id),), "lyric cursor"),
    )
    ambient = emit_particles(
        (Emission(str(i), 2 * i / 17) for i in range(18)),
        lambda ctx: petal(ctx, spread=1000),
        id="ambient",
        seed=17,
        emitter=lambda time: Vec2(140, 90),
    )
    straight = emit_particles(
        (Emission(str(i), 0.25 * i) for i in range(6)),
        lambda ctx: petal(ctx, spread=1000, linear=True),
        id="straight",
        seed=17,
        emitter=lambda time: Vec2(140, -30),
    )
    triggered = emit_particles(
        (Emission(str(i), front.start + front.duration * i / 12) for i in range(12)),
        petal,
        id="sung",
        seed=17,
        emitter=lambda time: cursor.at(time).position,
        origin=cursor.origin,
    )
    scene = Scene(document).add(
        lyrics,
        *ambient,
        *straight,
        *triggered,
        cursor,
        *echoes(cursor),
    )
    scene.replace_source(record_index)
    return scene
