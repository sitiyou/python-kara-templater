from dataclasses import replace

import pytest

from kara_templater import (
    BLACK,
    WHITE,
    AnimationClip,
    ColorRamp,
    ColorStop,
    Document,
    Lifetime,
    LinearGradient,
    ObjectGroup,
    PathFunction,
    PathObject,
    RectangleClip,
    Scene,
    SceneBudget,
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
        .compile()
        .document.dumps(),
        time,
        (320, 240),
    ).rgba


@pytest.mark.parametrize("gradient", [False, True])
def test_local_rectangle_matches_explicit_world_mask_with_parent_transform(gradient):
    leaf = node(
        state=VisualState(position=Vec2(20, 10), scale=Vec2(1.2, 1.2), rotation=15),
        clip=RectangleClip(0, 0, 50, 80, space="local"),
        material=LinearGradient(
            fill=ColorRamp((ColorStop(0, BLACK), ColorStop(320, WHITE)))
        )
        if gradient
        else None,
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
    local = (
        Scene(Document.create())
        .add(replace(moving, clip=RectangleClip(0, 0, 50, 80, space="local")))
        .compile()
    )
    screen = (
        Scene(Document.create())
        .add(replace(moving, clip=RectangleClip(0, 0, 50, 80)))
        .compile()
    )
    assert local.objects[0].strategy == "sampled"
    assert local.objects[0].peak_clip_points == 4
    assert screen.objects[0].strategy == "native-move"
    assert r"\clip(1,m" in local.document.lines[0].text
    assert r"\clip(0,0,50,80)" in screen.document.lines[0].text
    assert rendered(
        replace(moving, clip=RectangleClip(0, 0, 50, 80, space="local")), 1000
    ) != rendered(replace(moving, clip=RectangleClip(0, 0, 50, 80)), 1000)


def test_dynamic_empty_region_and_inverse_are_complementary():
    shape = VectorPath.rectangle(50, 80)
    deform = PathFunction(
        lambda path, time: None if time < 1 else path, max_points=4, breakpoints=(1,)
    )
    normal = node(clip=VectorClip(shape, deform=deform))
    inverse = replace(normal, clip=VectorClip(shape, inverse=True, deform=deform))
    assert not any(rendered(normal, 0))
    assert rendered(inverse, 0) == rendered(node(), 0)
    assert any(rendered(normal, 1000))
    assert rendered(normal, 1000) != rendered(inverse, 1000)
    first = Scene(Document.create()).add(normal).compile().document.dumps()
    assert first == Scene(Document.create()).add(normal).compile().document.dumps()


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
    copied = source.copy(id="later", delay=2, offset=Vec2(30, 0))
    Scene(Document.create()).add(copied).compile()
    assert min(calls) >= 0 and max(calls) < 2
    calls.clear()
    with pytest.raises(SceneCompileError, match="clip point budget"):
        Scene(Document.create()).add(copied).compile(
            budget=SceneBudget(max_path_points=4)
        )
    assert calls == []
    bad = replace(
        source,
        clip=VectorClip(
            VectorPath.rectangle(50, 80),
            deform=PathFunction(lambda path, time: VectorPath.circle(30), max_points=4),
        ),
    )
    with pytest.raises(SceneCompileError, match="clip callback exceeded"):
        Scene(Document.create()).add(bad).compile()


def test_vector_mask_combines_with_gradient_and_keeps_hole():
    outside = VectorPath.rectangle(100, 80)
    hole = VectorPath.polygon(Vec2(20, 20), Vec2(20, 60), Vec2(80, 60), Vec2(80, 20))
    masked = node(
        clip=VectorClip(VectorPath((*outside.contours, *hole.contours))),
        material=LinearGradient(
            fill=ColorRamp((ColorStop(0, BLACK), ColorStop(100, WHITE)))
        ),
    )
    image = rendered(masked)
    assert image[(40 * 320 + 50) * 4 + 3] == 0
    assert image[(10 * 320 + 50) * 4 + 3] > 250
    pixel = image[(10 * 320 + 50) * 4 : (10 * 320 + 50) * 4 + 3]
    assert max(abs(channel - 129) for channel in pixel) <= 1


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
        .compile()
    )
    assert result.objects[0].strategy == "native-static-affine-path"


def test_mask_callback_failures_include_object_time_and_source():
    from kara_templater import EventOrigin, SourceRef

    def broken(path, time):
        raise RuntimeError("mask failed")

    origin = EventOrigin((SourceRef("source"),), "mask")
    obj = node(
        origin=origin,
        clip=VectorClip(
            VectorPath.rectangle(20, 20), deform=PathFunction(broken, max_points=4)
        ),
    )
    with pytest.raises(
        SceneCompileError,
        match="sample at 0.010000s: clip callback: RuntimeError: mask failed",
    ) as caught:
        Scene(Document.create()).add(obj).compile()
    assert caught.value.object_id == "object"
    assert caught.value.origin == origin
