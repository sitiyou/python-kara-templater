from dataclasses import replace

import pytest

from kara_templater import (
    PINK,
    AssBudget,
    Document,
    EventOrigin,
    Lifetime,
    ObjectGroup,
    PathFunction,
    PathObject,
    RectangleClip,
    Scene,
    SceneCompileError,
    SourceRef,
    Vec2,
    VectorClip,
    VectorPath,
    VisualState,
)
from kara_templater._raster import rasterize


def child(id="child", **kwargs):
    return PathObject(
        id=id, lifetime=Lifetime(0, 2), path=VectorPath.rectangle(120, 80), **kwargs
    )


def compiled(*objects):
    return Scene(Document.create(width=320, height=240)).add(*objects).ass.compile()


def pixels(*objects, time=0):
    return rasterize(compiled(*objects).document.dumps(), time, (320, 240)).rgba


@pytest.mark.parametrize("inverse", (False, True))
def test_large_polygon_half_plane_matches_native_rectangle_after_blur(inverse):
    node = child(
        state=VisualState(position=Vec2(90, 30), blur=12, border=8, opacity=0.4),
    )
    polygon = VectorPath.polygon(
        Vec2(-65536, -65536),
        Vec2(160, -65536),
        Vec2(160, 65536),
        Vec2(-65536, 65536),
    )
    actual = pixels(replace(node, clip=VectorClip(polygon, inverse=inverse)))
    expected = pixels(
        replace(node, clip=RectangleClip(-65536, -65536, 160, 65536, inverse=inverse))
    )
    assert any(actual)
    bounded = VectorPath.polygon(Vec2(0, 0), Vec2(160, 0), Vec2(160, 240), Vec2(0, 240))
    assert actual == pixels(replace(node, clip=VectorClip(bounded, inverse=inverse)))
    # Native rectangle and vector-mask paths round the fill and border alpha
    # separately. Compare displayed RGB; transparent straight RGB is undefined.
    assert (
        max(abs(a - b) for a, b in zip(actual[3::4], expected[3::4], strict=True)) <= 2
    )
    for background in (0, 255):

        def displayed(data, background):
            return [
                round(
                    data[i + c] * data[i + 3] / 255
                    + background * (1 - data[i + 3] / 255)
                )
                for i in range(0, len(data), 4)
                for c in range(3)
            ]

        assert (
            max(
                abs(a - b)
                for a, b in zip(
                    displayed(actual, background),
                    displayed(expected, background),
                    strict=True,
                )
            )
            <= 1
        )


def test_shared_local_mask_uses_group_world_transform_not_child_transform():
    leaves = (
        child(
            "first",
            state=VisualState(position=Vec2(-20, 0), rotation=10),
        ),
        child(
            "second",
            state=VisualState(position=Vec2(40, 25), rotation=-20, fill=PINK),
        ),
    )
    state = VisualState(position=Vec2(100, 60), rotation=25, scale=Vec2(1.2, 0.8))
    parent = ObjectGroup(
        id="group",
        lifetime=Lifetime(0, 2),
        state=state,
        children=leaves,
        clip=RectangleClip(0, 0, 80, 70, space="local"),
    )
    # An independently defined world polygon, applied unchanged to both children.
    world = VectorPath.rectangle(80, 70).map(
        lambda p: state.position + Vec2(p.x * 1.2, p.y * 0.8).rotated(25)
    )
    reference = replace(
        parent,
        clip=None,
        children=tuple(replace(node, clip=VectorClip(world)) for node in leaves),
    )
    assert any(pixels(parent))
    assert pixels(parent) == pixels(reference)
    assert all(
        (report.peak_clip_points or 0) >= 4 for report in compiled(parent).objects
    )


def test_nested_rectangles_intersect_a_child_mask_with_holes():
    outer = VectorPath.rectangle(120, 80)
    hole = VectorPath.polygon(Vec2(40, 20), Vec2(40, 60), Vec2(80, 60), Vec2(80, 20))
    shape = VectorPath(outer.contours + hole.contours)
    leaf = child(clip=VectorClip(shape))
    inner = ObjectGroup(
        id="inner",
        lifetime=leaf.lifetime,
        children=(leaf,),
        clip=RectangleClip(10, 0, 100, 80),
    )
    group = ObjectGroup(
        id="group",
        lifetime=leaf.lifetime,
        children=(inner,),
        clip=RectangleClip(0, 10, 120, 70),
    )
    boundary = VectorPath.polygon(
        Vec2(10, 10), Vec2(100, 10), Vec2(100, 70), Vec2(10, 70)
    )
    expected = replace(
        leaf, clip=VectorClip(VectorPath(boundary.contours + hole.contours))
    )
    assert pixels(group) == pixels(expected)
    disjoint = replace(group, clip=RectangleClip(200, 200, 220, 220))
    assert not any(pixels(disjoint))


def test_inverse_group_mask_and_redundant_mask_share_standard_clip_semantics():
    mask = RectangleClip(20, 20, 80, 60, inverse=True)
    leaf = child()
    group = ObjectGroup(id="group", lifetime=leaf.lifetime, children=(leaf,), clip=mask)
    assert pixels(group) == pixels(replace(leaf, clip=mask))
    assert pixels(replace(group, children=(replace(leaf, clip=mask),))) == pixels(group)
    limited = replace(
        group, children=(replace(leaf, clip=RectangleClip(0, 0, 60, 80)),)
    )
    expected = VectorPath.polygon(
        Vec2(),
        Vec2(60, 0),
        Vec2(60, 20),
        Vec2(20, 20),
        Vec2(20, 60),
        Vec2(60, 60),
        Vec2(60, 80),
        Vec2(0, 80),
    )
    assert pixels(limited) == pixels(replace(leaf, clip=VectorClip(expected)))


def test_two_nonconvex_masks_intersect_instead_of_overwriting():
    path = VectorPath.polygon(
        Vec2(), Vec2(100, 0), Vec2(50, 30), Vec2(100, 80), Vec2(0, 80)
    )
    group = ObjectGroup(
        id="group",
        lifetime=Lifetime(0, 2),
        clip=VectorClip(path),
        children=(child(clip=VectorClip(path.map(lambda p: p + Vec2(5, 0)))),),
    )
    actual = pixels(group)[3::4]
    first = pixels(child(clip=group.clip))[3::4]
    second = pixels(group.children[0])[3::4]
    for result, a, b in zip(actual, first, second, strict=True):
        if a in (0, 255) and b in (0, 255):
            assert result == min(a, b)
    assert actual != first and actual != second


def test_group_mask_preflight_and_callback_errors_keep_group_origin():
    calls = []
    origin = EventOrigin((SourceRef("source"),), "group mask")

    def mask(path, time):
        calls.append(time)
        raise RuntimeError("broken group mask")

    group = ObjectGroup(
        id="group",
        lifetime=Lifetime(0, 2),
        origin=origin,
        children=(child(),),
        clip=VectorClip(
            VectorPath.rectangle(50, 50), deform=PathFunction(mask, max_points=8)
        ),
    )
    scene = Scene(Document.create()).add(group)
    with pytest.raises(SceneCompileError, match="declared clip point budget") as caught:
        scene.ass.compile(budget=AssBudget(max_path_points=4))
    assert caught.value.object_id == "group"
    assert caught.value.origin == origin
    assert calls == []


def test_group_rectangle_that_rounds_empty_obeys_normal_and_inverse_semantics():
    leaf = child(clip=VectorClip(VectorPath.circle(50)))
    group = ObjectGroup(
        id="group",
        lifetime=leaf.lifetime,
        children=(leaf,),
        clip=RectangleClip(0.1, 0.1, 0.2, 0.2),
    )
    assert compiled(group).event_count == 0
    assert pixels(
        replace(group, clip=RectangleClip(0.1, 0.1, 0.2, 0.2, inverse=True))
    ) == pixels(leaf)


@pytest.mark.parametrize(
    "first_inverse,second_inverse",
    [(False, False), (True, False), (False, True), (True, True)],
)
def test_all_inverse_combinations_match_vector_reference_and_native_interiors(
    first_inverse, second_inverse
):
    first = RectangleClip(10, 10, 80, 60, inverse=first_inverse)
    second = RectangleClip(40, 30, 100, 70, inverse=second_inverse)
    leaf = child(clip=second)
    group = ObjectGroup(
        id="group", lifetime=leaf.lifetime, children=(leaf,), clip=first
    )
    expected = bytes(
        min(a, b)
        for a, b in zip(
            pixels(child(clip=first))[3::4], pixels(leaf)[3::4], strict=True
        )
    )
    actual = pixels(group)[3::4]
    # General combinations lower to vector clips; libass rasterizes their
    # boundary coverage slightly differently from hard rectangle clipping.
    references = {
        (False, False): RectangleClip(40, 30, 80, 60),
        (True, False): VectorClip(
            VectorPath.polygon(
                Vec2(80, 30),
                Vec2(100, 30),
                Vec2(100, 70),
                Vec2(40, 70),
                Vec2(40, 60),
                Vec2(80, 60),
            )
        ),
        (False, True): VectorClip(
            VectorPath.polygon(
                Vec2(10, 10),
                Vec2(80, 10),
                Vec2(80, 30),
                Vec2(40, 30),
                Vec2(40, 60),
                Vec2(10, 60),
            )
        ),
        (True, True): VectorClip(
            VectorPath.polygon(
                Vec2(10, 10),
                Vec2(80, 10),
                Vec2(80, 30),
                Vec2(100, 30),
                Vec2(100, 70),
                Vec2(40, 70),
                Vec2(40, 60),
                Vec2(10, 60),
            ),
            inverse=True,
        ),
    }
    assert actual == pixels(child(clip=references[first_inverse, second_inverse]))[3::4]
    for y in range(240):
        for x in range(320):
            if (
                min(abs(x - edge) for edge in (10, 40, 80, 100)) > 1
                and min(abs(y - edge) for edge in (10, 30, 60, 70)) > 1
            ):
                assert actual[y * 320 + x] == expected[y * 320 + x]
    swapped = replace(group, clip=second, children=(replace(leaf, clip=first),))
    assert pixels(swapped)[3::4] == actual


def test_boolean_work_budget_reports_the_mask_owner():
    origin = EventOrigin((SourceRef("test"),), "boolean mask")
    leaf = child(origin=origin, clip=RectangleClip(10, 10, 80, 70))
    group = ObjectGroup(
        id="group",
        lifetime=leaf.lifetime,
        children=(leaf,),
        clip=RectangleClip(20, 20, 60, 60, inverse=True),
    )
    with pytest.raises(SceneCompileError, match="boolean work budget") as caught:
        Scene(Document.create()).add(group).ass.compile(
            budget=AssBudget(max_boolean_work=1)
        )
    assert caught.value.object_id == leaf.id
    assert caught.value.origin == origin


def test_shared_motion_and_mask_keep_parent_clock_across_child_exposures():
    from kara_templater import RectangleFunction, StateFunction

    calls = []

    def motion(state, progress):
        calls.append(progress)
        return replace(state, position=Vec2(7, 3 + progress * 10))

    leaves = (
        replace(
            child("first"),
            lifetime=Lifetime(0.1, 1.1),
            path=VectorPath.rectangle(30, 20),
            state=VisualState(position=Vec2(30, 20)),
        ),
        replace(
            child("second"),
            lifetime=Lifetime(0.3, 0.9),
            path=VectorPath.rectangle(30, 20),
            state=VisualState(position=Vec2(70, 20), fill=PINK),
        ),
    )
    mask = RectangleClip(
        0,
        0,
        120,
        80,
        space="local",
        deform=RectangleFunction(lambda t: (0, 0, 20 + 100 * t, 80)),
    )
    group = ObjectGroup(
        id="root", lifetime=Lifetime(0.1, 1.1), children=leaves, clip=mask
    ).animate(StateFunction(motion, frozenset(("position",))), duration=1)
    doc = Document.create(width=160, height=100)
    scene = Scene(doc).add(group)
    assert not calls
    assert scene.evaluator().at("second", 0.75).position == Vec2(77, 29.5)
