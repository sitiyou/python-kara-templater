from dataclasses import replace

import pytest

from kara_templater import (
    Document,
    Lifetime,
    PathObject,
    RectangleClip,
    RectangleFunction,
    Scene,
    SceneBudget,
    SceneCompileError,
    Vec2,
    VectorPath,
    VisualState,
)
from kara_templater._raster import rasterize


def shape(clip):
    return PathObject(
        id="box",
        lifetime=Lifetime(1, 3),
        path=VectorPath.rectangle(100, 50),
        state=VisualState(position=Vec2(30, 30)),
        clip=clip,
    )


def pixels(node, time):
    result = Scene(Document.create(width=200, height=140)).add(node).compile()
    return rasterize(result.document.dumps(), time, (200, 140)).rgba


def test_dynamic_rectangle_clock_empty_masks_inverse_and_copy():
    for inverse in (False, True):
        motion = RectangleFunction(
            lambda t: None if t < 0.5 else (30, 30, 80, 80), (0.5,)
        )
        node = shape(RectangleClip(0, 0, 1, 1, inverse=inverse, deform=motion))
        assert pixels(node, 1600) == pixels(
            shape(RectangleClip(30, 30, 80, 80, inverse=inverse)), 1600
        )
        assert (
            pixels(node, 1100) == pixels(shape(None), 1100)
            if inverse
            else not any(pixels(node, 1100))
        )
        assert pixels(node.copy(id="delayed", delay=2), 3600) == pixels(node, 1600)


def test_local_dynamic_rectangle_uses_native_axis_aligned_clip():
    node = shape(
        RectangleClip(
            0,
            0,
            1,
            1,
            space="local",
            deform=RectangleFunction(lambda t: (0, 0, 50, 50)),
        )
    )
    assert pixels(node, 1500) == pixels(shape(RectangleClip(30, 30, 80, 80)), 1500)
    mirrored = replace(
        node, state=VisualState(position=Vec2(130, 30), scale=Vec2(-1, 1))
    )
    reference = replace(mirrored, clip=RectangleClip(80, 30, 130, 80))
    assert pixels(mirrored, 1500) == pixels(reference, 1500)


def test_rectangle_callback_validation_and_preflight():
    calls = []

    def sample(time):
        calls.append(time)
        return (0, 0, 10, 10)

    node = shape(RectangleClip(0, 0, 1, 1, deform=RectangleFunction(sample)))
    with pytest.raises(SceneCompileError, match="budget"):
        Scene(Document.create()).add(node).compile(budget=SceneBudget(max_events=1))
    assert not calls
    with pytest.raises(ValueError, match="breakpoint"):
        shape(RectangleClip(0, 0, 1, 1, deform=RectangleFunction(sample, (3,))))
    bad = shape(
        RectangleClip(
            0, 0, 1, 1, deform=RectangleFunction(lambda t: (0, 0, float("nan"), 1))
        )
    )
    with pytest.raises(SceneCompileError):
        Scene(Document.create()).add(bad).compile()
