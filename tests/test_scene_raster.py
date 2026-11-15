from dataclasses import replace

import pytest

from kara_templater import (
    CYAN,
    PINK,
    AnimationClip,
    Document,
    Lifetime,
    NativeEvent,
    ObjectGroup,
    PathObject,
    RasterSettings,
    Scene,
    SceneBudget,
    StateFunction,
    StatePatch,
    Tween,
    Vec2,
    VectorPath,
    VisualState,
    rasterize_group,
)
from kara_templater._raster import rasterize


def group():
    lifetime = Lifetime(0, 0.1)
    return ObjectGroup(
        id="overlap",
        lifetime=lifetime,
        state=VisualState(opacity=0.5),
        children=tuple(
            PathObject(
                id=name,
                lifetime=lifetime,
                path=VectorPath.rectangle(40, 30),
                state=VisualState(position=position, fill=color),
            )
            for name, position, color in (
                ("cyan", Vec2(20, 20), CYAN),
                ("pink", Vec2(40, 30), PINK),
            )
        ),
    )


def pixels(node, time=10, opacity=1):
    scene = Scene(Document.create(width=100, height=80)).add(node)
    return rasterize(scene.compile().document.dumps(), time, (100, 80), opacity=opacity)


def test_root_alpha_follows_composition_and_identical_frames_merge():
    node = group()
    result = rasterize_group(node, resolution=(100, 80))
    assert result.sampled_frames == 5
    assert all(
        isinstance(event, NativeEvent) and event.event.end_time == 100
        for event in result.scene.objects
    )
    output = rasterize(result.scene.compile().document.dumps(), 10, (100, 80))
    reference = pixels(replace(node, state=replace(node.state, opacity=1)), opacity=0.5)
    assert output.rgba == reference.rgba
    assert output.rgba != pixels(node).rgba
    offset = (40 * 100 + 50) * 4
    assert output.rgba[offset : offset + 4] == bytes(
        (PINK.red, PINK.green, PINK.blue, 128)
    )


def test_dynamic_root_opacity_is_applied_once_and_seek_is_independent():
    node = replace(
        group(),
        state=VisualState(opacity=0),
        animations=(AnimationClip(0, 0.1, Tween(StatePatch(opacity=1))),),
    )
    result = rasterize_group(node, resolution=(100, 80))
    script = result.scene.compile().document.dumps()
    opaque = replace(node, state=VisualState(), animations=())
    for time in (90, 10, 50, 30, 70):
        actual = rasterize(script, time, (100, 80))
        assert (
            actual.rgba
            == pixels(opaque, time, opacity=node.at(time / 1000).opacity).rgba
        )


def test_raster_preflight_and_output_limits():
    calls = []

    def animate(state, progress):
        calls.append(progress)
        return state

    node = replace(
        group(),
        animations=(
            AnimationClip(0, 0.1, StateFunction(animate, frozenset(("position",)))),
        ),
    )
    with pytest.raises(ValueError, match="frame budget"):
        rasterize_group(
            node, resolution=(100, 80), settings=RasterSettings(max_frames=1)
        )
    assert not calls
    with pytest.raises(ValueError, match="pixel"):
        rasterize_group(
            node, resolution=(100, 80), settings=RasterSettings(max_pixels=10)
        )
    assert not calls
    with pytest.raises(ValueError, match="budget"):
        rasterize_group(
            group(), resolution=(100, 80), budget=SceneBudget(max_bytes=100)
        )


def test_blur_follows_child_composition_and_precedes_root_opacity():
    from kara_templater._material_raster import blur_frame
    from kara_templater._raster import RasterCanvas

    node = group()
    node = replace(
        node,
        children=tuple(
            replace(child, state=replace(child.state, opacity=0.7))
            for child in node.children
        ),
    )
    budget = SceneBudget(max_active=10_000)
    result = rasterize_group(node, resolution=(100, 80), blur_radius=2, budget=budget)
    actual = rasterize(
        result.scene.compile(budget=budget).document.dumps(), 50, (100, 80)
    )
    opaque = replace(node, state=replace(node.state, opacity=1))
    x, y, blurred = blur_frame(pixels(opaque), 2)
    canvas = RasterCanvas(100, 80)
    canvas.over_frame(blurred, x, y)
    reference = canvas.finish(opacity=0.5)
    assert actual.rgba == reference.rgba
    # An ordinary per-child blur/alpha produces a different overlap and edge.
    individual = replace(
        node,
        children=tuple(
            replace(child, state=replace(child.state, blur=2))
            for child in node.children
        ),
    )
    assert actual.rgba != pixels(individual).rgba


def test_short_child_lifetime_splits_coarse_output_grid():
    node = group()
    node = replace(
        node, children=(replace(node.children[0], lifetime=Lifetime(0.01, 0.02)),)
    )
    result = rasterize_group(node, resolution=(100, 80), budget=SceneBudget(fps=10))
    script = result.scene.compile().document.dumps()
    for time in (0, 15, 25, 99):
        assert (
            rasterize(script, time, (100, 80)).rgba
            == pixels(
                replace(node, state=replace(node.state, opacity=1)),
                time,
                opacity=node.state.opacity,
            ).rgba
        )
    assert result.sampled_frames == 3
    with pytest.raises(ValueError, match="boundary splitting"):
        rasterize_group(
            node,
            resolution=(100, 80),
            budget=SceneBudget(fps=10),
            settings=RasterSettings(max_frames=2),
        )


def test_descendant_origins_and_tracks_survive_composition():
    from kara_templater import EventOrigin, SourceRef

    node = group()
    refs = (SourceRef("line:1"), SourceRef("line:2"))
    node = replace(
        node,
        children=tuple(
            replace(child, origin=EventOrigin((ref,), "child", (f"track:{index}",)))
            for index, (child, ref) in enumerate(zip(node.children, refs, strict=True))
        ),
    )
    result = rasterize_group(node, resolution=(100, 80))
    assert result.scene.objects
    for item in result.scene.objects:
        assert item.origin == EventOrigin(
            refs, "offscreen group", ("track:0", "track:1")
        )


@pytest.mark.parametrize("radius", [-1, 101, float("nan"), float("inf")])
def test_invalid_blur_is_rejected(radius):
    with pytest.raises(ValueError):
        rasterize_group(group(), resolution=(100, 80), blur_radius=radius)


def test_root_geometry_mask_and_delayed_copy_keep_their_clock():
    from kara_templater import RectangleClip

    node = replace(
        group(),
        clip=RectangleClip(30, 10, 75, 70, space="screen"),
        animations=(AnimationClip(0, 0.1, Tween(StatePatch(position=Vec2(10, 0)))),),
    )
    original = rasterize_group(node, resolution=(100, 80))
    delayed = rasterize_group(node.copy(id="later", delay=2), resolution=(100, 80))
    source = replace(node, state=replace(node.state, opacity=1))
    for time in (90, 10, 50, 30, 70):
        actual = rasterize(original.scene.compile().document.dumps(), time, (100, 80))
        assert actual.rgba == pixels(source, time, opacity=0.5).rgba
        assert (
            actual.rgba
            == rasterize(
                delayed.scene.compile().document.dumps(), time + 2000, (100, 80)
            ).rgba
        )
