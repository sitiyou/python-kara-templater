"""Static gradient bands retain a perpendicular native karaoke clip."""

from dataclasses import replace

import pytest

from kara_templater import (
    AnimationClip,
    Color,
    ColorRamp,
    ColorStop,
    Document,
    FadeIn,
    Lifetime,
    LinearGradient,
    ObjectGroup,
    PathObject,
    RectangleClip,
    RectangleKeyframes,
    Scene,
    SceneBudget,
    StatePatch,
    TextObject,
    Tween,
    Vec2,
    VectorPath,
    VisualState,
)
from kara_templater._raster import rasterize


@pytest.mark.parametrize("axis", ("x", "y"))
@pytest.mark.parametrize("text", (False, True))
def test_native_gradient_matches_independent_static_clips(axis, text):
    doc = Document.create(width=64, height=64)
    ramp = ColorRamp(
        (ColorStop(8, Color.hex("#80EEFF")), ColorStop(40, Color.hex("#EE7088")))
    )
    material = LinearGradient(axis=axis, fill=ramp, outline=ramp, step=1)
    bounds = lambda edge: (0, 0, edge, 24) if axis == "y" else (0, 0, 24, edge)
    keys = RectangleKeyframes(
        (
            (0, bounds(0)),
            (0.2, bounds(24)),
            (0.4, bounds(24)),
            (0.4, bounds(6)),
            (0.6, bounds(24)),
            (1, bounds(24)),
        )
    )
    state = VisualState(position=Vec2(8, 8), scale=Vec2(1.25, 1.25), border=1, blur=0.5)
    mask = RectangleClip(0, 0, 24, 24, space="local", deform=keys)
    node = (
        TextObject(
            id="word",
            lifetime=Lifetime(0, 1),
            text="Aa",
            font_size=20,
            state=state,
            clip=mask,
            material=material,
        )
        if text
        else PathObject(
            id="shape",
            lifetime=Lifetime(0, 1),
            path=VectorPath.rectangle(24, 24),
            state=state,
            clip=mask,
            material=material,
        )
    )
    scene = Scene(doc).add(node)
    result = scene.compile(
        native_tweens=True, budget=SceneBudget(fps=60, max_events=100)
    )
    assert result.objects[0].strategy == "native-clip-bands"
    assert result.event_count <= 60
    assert (
        scene.compile(native_tweens=True, budget=SceneBudget(fps=10)).event_count
        == result.event_count
    )
    for ms in (0, 100, 200, 350, 400, 500, 600, 950):
        coords = keys.bounds_at(ms / 1000)
        reference_scene = Scene(doc)
        if coords[2] > coords[0] and coords[3] > coords[1]:
            # Native rectangle coordinates use the existing integer clip contract.
            world = tuple(round(8 + coordinate * 1.25) for coordinate in coords)
            reference_scene.add(
                replace(
                    node, clip=RectangleClip(world[0], world[1], world[2], world[3])
                )
            )
        reference = reference_scene.compile()
        assert (
            rasterize(result.document.dumps(), ms, (64, 64)).rgba
            == rasterize(reference.document.dumps(), ms, (64, 64)).rgba
        )


def test_native_gradient_keeps_inherited_fade_and_outline():
    doc = Document.create(width=32, height=32)
    ramp = ColorRamp(
        (ColorStop(0, Color.hex("#FFFF00")), ColorStop(32, Color.hex("#FF0000")))
    )
    node = PathObject(
        id="shape",
        lifetime=Lifetime(0, 1),
        path=VectorPath.rectangle(32, 32),
        material=LinearGradient(axis="y", fill=ramp),
        state=VisualState(outline=Color.hex("#0000FF"), border=2),
        clip=RectangleClip(
            0,
            0,
            32,
            32,
            deform=RectangleKeyframes(((0, (0, 0, 0, 32)), (1, (0, 0, 32, 32)))),
        ),
    )
    group = ObjectGroup(
        id="group",
        lifetime=node.lifetime,
        children=(node,),
        animations=(AnimationClip(0, 0.25, FadeIn()),),
    )
    result = Scene(doc).add(group).compile(native_tweens=True)
    assert result.objects[0].strategy == "native-clip-bands"
    # libass truncates interpolated ASS alpha; match its 8-bit value explicitly.
    for ms in (125, 250, 500, 750):
        ref = replace(
            node,
            state=replace(
                node.state, opacity=(255 - int(255 * max(0, 1 - ms / 250))) / 255
            ),
            clip=RectangleClip(0, 0, 32 * ms / 1000, 32),
        )
        reference = Scene(doc).add(ref).compile()
        assert (
            rasterize(result.document.dumps(), ms, (32, 32)).rgba
            == rasterize(reference.document.dumps(), ms, (32, 32)).rgba
        )


@pytest.mark.parametrize("unsupported", ("inverse", "crossing", "color", "motion"))
def test_other_material_clip_combinations_keep_sampling(unsupported):
    ramp = ColorRamp(
        (ColorStop(0, Color.hex("#FFFFFF")), ColorStop(32, Color.hex("#FF0000")))
    )
    keys = RectangleKeyframes(((0, (0, 0, 0, 32)), (1, (0, 0, 32, 32))))
    node = PathObject(
        id="shape",
        lifetime=Lifetime(0, 1),
        path=VectorPath.rectangle(32, 32),
        material=LinearGradient(axis="y", fill=ramp),
        clip=RectangleClip(0, 0, 32, 32, deform=keys, inverse=unsupported == "inverse"),
    )
    if unsupported == "crossing":
        node = replace(node, material=LinearGradient(axis="x", fill=ramp))
    elif unsupported in ("color", "motion"):
        patch = (
            StatePatch(fill=Color.hex("#00FF00"))
            if unsupported == "color"
            else StatePatch(position=Vec2(3, 0))
        )
        node = node.animate(Tween(patch), duration=1)
    result = (
        Scene(Document.create(width=32, height=32))
        .add(node)
        .compile(native_tweens=True)
    )
    assert result.objects[0].strategy == "sampled-bands"
