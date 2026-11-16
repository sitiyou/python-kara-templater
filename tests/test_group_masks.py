from dataclasses import replace

import pytest

from kara_templater import (
    CYAN,
    PINK,
    ColorRamp,
    ColorStop,
    Document,
    EventOrigin,
    FollowObject,
    Lifetime,
    LinearGradient,
    ObjectGroup,
    PathFunction,
    PathObject,
    RectangleClip,
    Scene,
    SceneBudget,
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
    return Scene(Document.create(width=320, height=240)).add(*objects).compile()


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


@pytest.mark.parametrize("gradient", [False, True])
def test_shared_local_mask_uses_group_world_transform_not_child_transform(gradient):
    material = (
        LinearGradient(fill=ColorRamp((ColorStop(0, CYAN), ColorStop(320, PINK))))
        if gradient
        else None
    )
    leaves = (
        child(
            "first",
            state=VisualState(position=Vec2(-20, 0), rotation=10),
            material=material,
        ),
        child(
            "second",
            state=VisualState(position=Vec2(40, 25), rotation=-20, fill=PINK),
            material=material,
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


def test_dynamic_group_mask_keeps_owner_clock_when_child_lifetime_and_copy_differ():
    calls = []

    def reveal(path, time):
        calls.append(time)
        return path if time >= 0.637 else None

    leaf = replace(child(), lifetime=Lifetime(1.5, 3))
    group = ObjectGroup(
        id="group",
        lifetime=Lifetime(1, 3),
        children=(leaf,),
        clip=VectorClip(
            VectorPath.rectangle(50, 80),
            space="local",
            deform=PathFunction(reveal, max_points=4, breakpoints=(0.637,)),
        ),
    )
    original = compiled(group)
    assert original.objects[0].strategy == "sampled"
    assert min(calls) == pytest.approx(0.51)
    assert (
        min(line.start_time for line in original.document.lines if not line.comment)
        == 1640
    )
    assert original.max_time_quantization == pytest.approx(0.003)
    before = tuple(calls)
    calls.clear()
    duplicate = compiled(group.copy(id="later", delay=2))
    assert calls == pytest.approx(before)
    assert [
        (line.start_time + 2000, line.end_time + 2000, line.text)
        for line in original.document.lines
    ] == [
        (line.start_time, line.end_time, line.text) for line in duplicate.document.lines
    ]


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
        scene.compile(budget=SceneBudget(max_path_points=4))
    assert caught.value.object_id == "group"
    assert caught.value.origin == origin
    assert calls == []
    with pytest.raises(
        SceneCompileError,
        match="sample at 0.010000s: clip callback: RuntimeError: broken group mask",
    ) as caught:
        scene.compile()
    assert caught.value.object_id == "group"
    assert caught.value.origin == origin


def test_static_sibling_masks_share_cached_owner_resolution():
    # Two short dynamic lifetimes produce the same single sampling instant.
    calls = []

    def mask(path, time):
        calls.append(time)
        return path

    group = ObjectGroup(
        id="group",
        lifetime=Lifetime(0, 0.01),
        children=(child("first"), child("second")),
        clip=VectorClip(
            VectorPath.rectangle(60, 60), deform=PathFunction(mask, max_points=4)
        ),
    )
    result = compiled(group)
    assert result.event_count == 2
    assert calls == [0.005]


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


def test_singular_local_group_mask_respects_inverse_when_child_overrides_world_state():
    anchor = ObjectGroup(
        id="anchor",
        lifetime=Lifetime(0, 2),
        children=(),
        state=VisualState(position=Vec2(100, 80)),
    )
    leaf = child(
        reference=FollowObject(
            "anchor", channels=frozenset(("position", "scale", "rotation", "skew"))
        )
    )
    group = ObjectGroup(
        id="group",
        lifetime=leaf.lifetime,
        children=(leaf,),
        state=VisualState(scale=Vec2(0, 1)),
        clip=RectangleClip(0, 0, 100, 100, space="local"),
    )
    assert compiled(anchor, group).event_count == 0
    inverse = replace(
        group, clip=RectangleClip(0, 0, 100, 100, space="local", inverse=True)
    )
    assert pixels(anchor, inverse) == pixels(
        replace(leaf, reference=None, state=anchor.state)
    )


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


@pytest.mark.parametrize("vector", [False, True])
def test_inverse_mask_with_color_field_matches_integer_pixel_exclusion(vector):
    shape = VectorPath.rectangle(40, 30).map(lambda p: p + Vec2(20, 10))
    clip = (
        VectorClip(shape, inverse=True)
        if vector
        else RectangleClip(20, 10, 60, 40, inverse=True)
    )
    field = LinearGradient(
        fill=ColorRamp((ColorStop(0, CYAN), ColorStop(320, PINK))), step=8
    )
    leaf = child(material=field)
    expected = bytearray(pixels(leaf))
    for y in range(10, 40):
        for x in range(20, 60):
            index = (y * 320 + x) * 4
            expected[index : index + 4] = bytes(4)
    actual = pixels(replace(leaf, clip=clip))
    if not vector:
        assert actual == bytes(expected)
    else:
        # Compare displayed RGB on both extreme backgrounds, not unassociated
        # RGB hidden behind zero alpha. The declared fixture bound is 4/255.
        for background in (0, 255):
            for index in range(0, len(actual), 4):
                for channel in range(3):
                    value = (
                        actual[index + channel] * actual[index + 3]
                        + background * (255 - actual[index + 3])
                        + 127
                    ) // 255
                    reference = (
                        expected[index + channel] * expected[index + 3]
                        + background * (255 - expected[index + 3])
                        + 127
                    ) // 255
                    assert abs(value - reference) <= 4


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
        Scene(Document.create()).add(group).compile(
            budget=SceneBudget(max_boolean_work=1)
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
    with pytest.raises(SceneCompileError, match="budget"):
        scene.compile(budget=SceneBudget(max_events=1))
    assert not calls
    budget = SceneBudget(fps=10)
    output = scene.compile(budget=budget).document.dumps()
    for time in (750, 350, 950):
        local = time / 1000 - 0.1
        fixed = replace(
            group,
            animations=(),
            state=VisualState(position=Vec2(7, 3 + local * 10)),
            clip=replace(mask, right=20 + 100 * local, deform=None),
        )
        reference = Scene(doc).add(fixed).compile(budget=budget).document.dumps()
        pixels = rasterize(output, time, (160, 100)).rgba
        assert any(pixels[3::4])
        assert pixels == rasterize(reference, time, (160, 100)).rgba
    assert scene.evaluator().at("second", 0.75).position == Vec2(77, 29.5)
