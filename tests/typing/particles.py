"""Procedural object APIs preserve concrete factory and copying types."""

from typing import assert_type

from kara_templater import (
    Emission,
    Lifetime,
    MoveAlong,
    ObjectGroup,
    ParticleContext,
    ParticleFactory,
    PathItem,
    PathObject,
    Polyline,
    SceneObject,
    Vec2,
    VectorPath,
    echoes,
    emit_particles,
    layout_path,
    split_path,
)


def custom(ctx: ParticleContext) -> PathObject:
    assert_type(ctx.uniform("size", 1, 5), float)
    return PathObject(
        id=ctx.id,
        lifetime=Lifetime(ctx.birth, ctx.birth + 2),
        path=VectorPath.rectangle(5, 5),
    )


def author() -> ObjectGroup:
    factory: ParticleFactory = custom
    objects = emit_particles((Emission("a", 0),), factory)
    assert_type(objects, tuple[SceneObject, ...])
    path = Polyline((Vec2(), Vec2(100, 0)))
    assert_type(MoveAlong(path).native_linear, bool)
    node = custom(ParticleContext("test", 0, 1, Vec2(), None))
    assert_type(echoes(node), tuple[PathObject, ...])
    assert_type(split_path(node, rows=2, columns=2), tuple[PathObject, ...])
    return layout_path((PathItem(node, 10),), path)
