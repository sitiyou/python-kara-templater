"""Custom lyric particles share the existing context and relative animation API."""

from typing import assert_type

from kara_templater import (
    CurveIn,
    DriftOut,
    Lifetime,
    LyricEcho,
    LyricHighlights,
    LyricLine,
    LyricParticles,
    LyricRule,
    ParticleContext,
    PathObject,
    Polyline,
    StatePatch,
    TrailPath,
    Transform,
    Vec2,
    VectorPath,
    VisualState,
)


def dot(context: ParticleContext) -> PathObject:
    assert_type(context.position, Vec2)
    return PathObject(
        id=context.id, lifetime=Lifetime(context.birth, context.birth + 0.4),
        path=VectorPath.rectangle(2, 2), state=VisualState(position=context.position),
    ).animate(Transform(
        offset=lambda p: Vec2(0, -20 * p), opacity=lambda p: 1 - p,
    ), duration=0.4)


def decorate(line: LyricLine) -> LyricLine:
    revealed = LyricHighlights.from_timing(StatePatch(), base_paint=StatePatch(opacity=0))(line)
    copied = LyricEcho(animation=CurveIn(), delay=-0.1)(revealed)
    result = LyricParticles(factory=dot, placement="line")(copied)
    assert_type(result, LyricLine)
    scheduled = result.schedule(
        LyricRule("character", "after_timing", DriftOut(), duration=0.5),
    )
    assert_type(scheduled, LyricLine)
    return scheduled


def trail(context: ParticleContext) -> PathObject:
    geometry = TrailPath(Polyline((Vec2(), Vec2(30, -20))))
    assert_type(geometry.line, Polyline)
    return PathObject(id=context.id, lifetime=Lifetime(context.birth, context.birth + 1.2),
                      path=geometry.full_path, deform=geometry)
