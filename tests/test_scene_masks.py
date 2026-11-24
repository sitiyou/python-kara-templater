from dataclasses import replace

import pytest

from kara_templater import (
    AnimationClip,
    AssBudget,
    Document,
    Lifetime,
    ObjectGroup,
    PathFunction,
    PathObject,
    RectangleClip,
    Scene,
    SceneCompileError,
    StatePatch,
    Tween,
    Vec2,
    VectorClip,
    VectorPath,
    VisualState,
)
from kara_templater._raster import rasterize


def node(**kwargs):
    return PathObject(
        id="object",
        lifetime=Lifetime(0, 2),
        path=VectorPath.rectangle(100, 80),
        **kwargs,
    )


def rendered(obj, time=0):
    return rasterize(
        Scene(Document.create(width=320, height=240))
        .add(obj)
        .ass.compile()
        .document.dumps(),
        time,
        (320, 240),
    ).rgba


def test_local_rectangle_matches_explicit_world_mask_with_parent_transform():
    leaf = node(
        state=VisualState(position=Vec2(20, 10), scale=Vec2(1.2, 1.2), rotation=15),
        clip=RectangleClip(0, 0, 50, 80, space="local"),
    )
    parent_state = VisualState(
        position=Vec2(100, 40), scale=Vec2(1.1, 1.1), rotation=20
    )
    parent = ObjectGroup(
        id="parent", lifetime=Lifetime(0, 2), state=parent_state, children=(leaf,)
    )

    def point(p):
        local = leaf.state.position + (p * 1.2).rotated(15)
        return parent_state.position + (local * 1.1).rotated(20)

    path = VectorPath.polygon(
        *(point(p) for p in (Vec2(), Vec2(50, 0), Vec2(50, 80), Vec2(0, 80)))
    )
    explicit = replace(parent, children=(replace(leaf, clip=VectorClip(path)),))
    assert rendered(parent) == rendered(explicit)


def test_local_mask_samples_motion_screen_mask_keeps_native_move():
    moving = node(
        animations=(AnimationClip(0, 2, Tween(StatePatch(position=Vec2(100, 0)))),)
    )
    screen = (
        Scene(Document.create())
        .add(replace(moving, clip=RectangleClip(0, 0, 50, 80)))
        .ass.compile()
    )
    assert screen.objects[0].strategy == "native-move"
    assert r"\clip(0,0,50,80)" in screen.document.lines[0].text


def test_mask_callback_clock_survives_copy_and_budgets_precede_execution():
    calls = []

    def sample(path, time):
        calls.append(time)
        return path

    source = node(
        clip=VectorClip(
            VectorPath.rectangle(50, 80),
            space="local",
            deform=PathFunction(sample, max_points=5, breakpoints=(1,)),
        )
    )
    with pytest.raises(SceneCompileError, match="clip point budget"):
        Scene(Document.create()).add(source).ass.compile(
            budget=AssBudget(max_path_points=4)
        )
    assert calls == []


def test_invalid_mask_combinations_have_explicit_diagnostics():
    with pytest.raises(ValueError, match="breakpoint"):
        node(
            clip=VectorClip(
                VectorPath.rectangle(20, 20),
                deform=PathFunction(
                    lambda path, time: path, max_points=4, breakpoints=(3,)
                ),
            )
        )
    result = (
        Scene(Document.create())
        .add(
            node(
                clip=RectangleClip(0, 0, 50, 80, space="local"),
                state=VisualState(skew=Vec2(0.2, 0)),
            )
        )
        .ass.compile()
    )
    assert result.objects[0].strategy == "native-static-affine-path"
