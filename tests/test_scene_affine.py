from dataclasses import replace

import pytest

from kara_templater import (
    Affine2D,
    AnimationClip,
    Document,
    Lifetime,
    Line,
    ObjectGroup,
    PathObject,
    RectangleClip,
    Scene,
    SceneBudget,
    SceneCompileError,
    StateFunction,
    StatePatch,
    TextObject,
    Tween,
    Vec2,
    VectorClip,
    VectorPath,
    VisualState,
    layout_document_text,
    outline_text,
)
from kara_templater._raster import rasterize


def transform(state, point):
    # Independent geometric definition, without Affine2D/composition helpers.
    sheared = Vec2(point.x + state.skew.x * point.y, point.y + state.skew.y * point.x)
    scaled = Vec2(sheared.x * state.scale.x, sheared.y * state.scale.y)
    return state.position + scaled.rotated(state.rotation)


def test_matrix_order_and_nested_decomposition_match_direct_geometry():
    a = Affine2D(2, 0, 0, 3, 10, 20)
    b = Affine2D(1, 0, 0.5, 1, 5, 2)
    assert (a @ b).apply(Vec2(3, 4)) == a.apply(b.apply(Vec2(3, 4)))
    parent = VisualState(
        position=Vec2(150, 80), scale=Vec2(2, 0.7), rotation=31, skew=Vec2(0.2, 0.1)
    )
    child = VisualState(
        position=Vec2(10, 20), scale=Vec2(0.8, 1.5), rotation=47, skew=Vec2(-0.1, 0.2)
    )
    leaf = PathObject(
        id="path",
        lifetime=Lifetime(0, 2),
        path=VectorPath.rectangle(60, 40),
        state=child,
    )
    group = ObjectGroup(
        id="group", lifetime=leaf.lifetime, state=parent, children=(leaf,)
    )
    result = Scene(Document.create()).add(group).evaluator().at("path", 0)
    for point in (Vec2(), Vec2(20, 30), Vec2(-50, 100)):
        expected = transform(parent, transform(child, point))
        actual = result.transform.apply(point)
        assert (actual.x, actual.y) == pytest.approx((expected.x, expected.y))


@pytest.mark.parametrize("text", [False, True])
def test_affine_geometry_and_local_mask_match_explicit_world_paths(text):
    lifetime = Lifetime(0, 2)
    child = VisualState(position=Vec2(15, 20), rotation=35)
    parent = VisualState(
        position=Vec2(120, 80), scale=Vec2(1.8, 0.7), rotation=15, skew=Vec2(0.2, 0)
    )
    shape = VectorPath.rectangle(80, 50)
    leaf = (
        TextObject(
            id="leaf",
            lifetime=lifetime,
            text="AB",
            font_size=48,
            alignment=7,
            state=child,
        )
        if text
        else PathObject(id="leaf", lifetime=lifetime, path=shape, state=child)
    )
    if isinstance(leaf, TextObject):
        shape = outline_text(leaf).path
        assert shape is not None
    leaf = replace(leaf, clip=RectangleClip(0, 0, 35, 50, space="local"))
    group = ObjectGroup(id="group", lifetime=lifetime, state=parent, children=(leaf,))
    doc = Document.create(width=320, height=240)
    output = Scene(doc).add(group).compile()
    origin = transform(parent, child.position)

    def world(point):
        return transform(parent, transform(child, point))

    mask = VectorPath.rectangle(35, 50).map(world)
    expected = PathObject(
        id="expected",
        lifetime=lifetime,
        path=shape.map(lambda p: world(p) - origin),
        state=VisualState(position=origin),
        clip=VectorClip(mask),
    )
    reference = Scene(doc).add(expected).compile()
    pixels = rasterize(output.document.dumps(), 0, (320, 240)).rgba
    assert any(pixels)
    assert pixels == rasterize(reference.document.dumps(), 0, (320, 240)).rgba
    assert output.objects[0].strategy == "native-static-affine-path"


def test_animated_affine_is_seekable_and_checks_outline_budget():
    leaf = TextObject(
        id="leaf",
        lifetime=Lifetime(0, 2),
        text="AV",
        font_size=48,
        animations=(AnimationClip(0, 2, Tween(StatePatch(rotation=80))),),
    )
    group = ObjectGroup(
        id="group",
        lifetime=leaf.lifetime,
        state=VisualState(position=Vec2(100, 100), scale=Vec2(1.6, 0.8)),
        children=(leaf,),
    )
    scene = Scene(Document.create()).add(group)
    evaluator = scene.evaluator()
    expected = evaluator.at("leaf", 1)
    evaluator.at("leaf", 1.8)
    evaluator.at("leaf", 0)
    assert evaluator.at("leaf", 1) == expected
    output = scene.compile()
    assert output.objects[0].strategy == "sampled-affine-path"
    assert output.document.dumps() == scene.compile().document.dumps()
    with pytest.raises(SceneCompileError, match="outline point budget") as caught:
        scene.compile(budget=SceneBudget(max_path_points=4))
    assert caught.value.object_id == "leaf"


def test_singular_group_is_empty_and_multiline_outline_has_explicit_diagnostic():
    leaf = TextObject(id="leaf", lifetime=Lifetime(0, 1), text="A")
    group = ObjectGroup(
        id="group",
        lifetime=leaf.lifetime,
        state=VisualState(skew=Vec2(1, 1)),
        children=(leaf,),
    )
    assert Scene(Document.create()).add(group).compile().event_count == 0
    with pytest.raises(SceneCompileError, match="single-line"):
        Scene(Document.create()).add(
            replace(leaf, text="A\nB", state=VisualState(skew=Vec2(0.2, 0)))
        ).compile()


def test_outline_preflight_runs_before_property_callbacks():
    calls = []

    def rotate(state, progress):
        calls.append(progress)
        return replace(state, rotation=progress * 60)

    word = TextObject(
        id="word",
        text="BUDGET",
        lifetime=Lifetime(0, 1),
        animations=(
            AnimationClip(0, 1, StateFunction(rotate, frozenset(("rotation",)))),
        ),
    )
    group = ObjectGroup(
        id="group",
        lifetime=word.lifetime,
        children=(word,),
        state=VisualState(scale=Vec2(2, 1)),
    )
    with pytest.raises(SceneCompileError, match="outline point budget"):
        Scene(Document.create()).add(group).compile(
            budget=SceneBudget(max_path_points=4)
        )
    assert calls == []


def test_document_range_bounds_include_animated_shear():
    document = Document.create()
    document.records.append(Line(text="AB", end_time=2000))
    layout = layout_document_text(document, len(document.records) - 1)
    changed = tuple(
        replace(
            item,
            object=replace(
                item.object,
                animations=(AnimationClip(0, 1, Tween(StatePatch(skew=Vec2(0.5, 0)))),),
            ),
        )
        for item in layout.characters
    )
    animated = replace(layout, characters=changed)
    original = layout.range_bounds(0, 2)
    actual = animated.range_bounds(0, 2, time=1)
    assert actual.left == pytest.approx(original.left)
    assert actual.top == pytest.approx(original.top)
    assert actual.width == pytest.approx(original.width + original.height * 0.5)
    assert actual.height == pytest.approx(original.height)


@pytest.mark.parametrize("scale", [Vec2(-1.8, 0.7), Vec2(1.8, -0.7), Vec2(-1.8, -0.7)])
def test_reflected_parent_and_child_rotation_match_explicit_outline(scale):
    lifetime = Lifetime(0, 2)
    child = VisualState(position=Vec2(10, 5), rotation=30)
    parent = VisualState(position=Vec2(160, 120), scale=scale, rotation=15)
    word = TextObject(
        id="word", text="AB", lifetime=lifetime, alignment=7, font_size=40, state=child
    )
    group = ObjectGroup(
        id="group",
        lifetime=lifetime,
        state=parent,
        children=(word,),
        clip=RectangleClip(-10, -10, 100, 80, space="local"),
    )
    outline = outline_text(word).path
    assert outline is not None
    origin = transform(parent, child.position)
    expected = PathObject(
        id="expected",
        lifetime=lifetime,
        path=outline.map(lambda p: transform(parent, transform(child, p)) - origin),
        state=VisualState(position=origin),
        clip=VectorClip(
            VectorPath.polygon(
                Vec2(-10, -10), Vec2(100, -10), Vec2(100, 80), Vec2(-10, 80)
            ).map(lambda p: transform(parent, p))
        ),
    )
    doc = Document.create(width=320, height=240)
    actual = Scene(doc).add(group).compile()
    reference = Scene(doc).add(expected).compile()
    rgba = rasterize(actual.document.dumps(), 0, (320, 240)).rgba
    assert any(rgba)
    assert rgba == rasterize(reference.document.dumps(), 0, (320, 240)).rgba
    assert actual.objects[0].strategy == "native-static-affine-path"
    assert r"\fscx-" not in actual.document.dumps()
    assert r"\fscy-" not in actual.document.dumps()


@pytest.mark.parametrize(
    "parent, child",
    [
        (VisualState(scale=Vec2(0, 1), rotation=23), VisualState(rotation=47)),
        (VisualState(scale=Vec2(0, 1), rotation=23), VisualState(skew=Vec2(0.2, 0))),
        (VisualState(scale=Vec2(0, 0)), VisualState(rotation=47)),
        (VisualState(skew=Vec2(1, 1), rotation=23), VisualState(rotation=47)),
    ],
)
def test_singular_composition_retains_queryable_geometry_but_no_filled_events(
    parent, child
):
    node = PathObject(
        id="shape",
        lifetime=Lifetime(0, 2),
        path=VectorPath.rectangle(80, 50),
        state=replace(child, position=Vec2(10, 20), border=3),
    )
    group = ObjectGroup(
        id="group",
        lifetime=node.lifetime,
        state=replace(parent, position=Vec2(100, 100)),
        children=(node,),
    )
    scene = Scene(Document.create()).add(group)
    state = scene.evaluator().at("shape", 1)
    assert state.singular
    for point in (Vec2(), Vec2(20, 30), Vec2(-5, 10)):
        expected = transform(group.state, transform(node.state, point))
        actual = state.transform.apply(point)
        assert (actual.x, actual.y) == pytest.approx((expected.x, expected.y))
    assert scene.compile().event_count == 0


def test_scale_crosses_zero_without_negative_ass_tags_or_backend_switch():
    node = TextObject(
        id="mirror",
        text="MIRROR",
        lifetime=Lifetime(0, 2),
        alignment=5,
        state=VisualState(position=Vec2(160, 120)),
        animations=(AnimationClip(0, 1.98, Tween(StatePatch(scale=Vec2(-1, 1)))),),
    )
    scene = Scene(Document.create(width=320, height=240)).add(node)
    assert scene.evaluator().at("mirror", 0.99).singular
    output = scene.compile()
    assert output.objects[0].strategy == "sampled-affine-path"
    events = [line for line in output.document.lines if not line.comment]
    assert all(
        r"\p1" in line.text and r"\fscx100.000000" in line.text for line in events
    )
    assert not any(line.start_time <= 990 < line.end_time for line in events)
    assert any(rasterize(output.document.dumps(), 0, (320, 240)).rgba)
    assert any(rasterize(output.document.dumps(), 1900, (320, 240)).rgba)
    assert not any(rasterize(output.document.dumps(), 990, (320, 240)).rgba)


def test_near_singular_group_is_not_rejected_by_an_absolute_determinant_threshold():
    leaf = TextObject(
        id="leaf", text="A", lifetime=Lifetime(0, 1), state=VisualState(rotation=45)
    )
    group = ObjectGroup(
        id="group",
        lifetime=leaf.lifetime,
        children=(leaf,),
        state=VisualState(scale=Vec2(1e-12, 1)),
    )
    state = Scene(Document.create()).add(group).evaluator().at("leaf", 0)
    assert not state.singular
    point = Vec2(1, 2)
    expected = transform(group.state, transform(leaf.state, point))
    actual = state.transform.apply(point)
    assert (actual.x, actual.y) == pytest.approx((expected.x, expected.y), abs=1e-15)


def test_layout_keeps_measurement_scale_when_objects_are_mirrored_or_collapsed():
    document = Document.create()
    document.records.append(Line(text="AB", end_time=2000))
    layout = layout_document_text(document, len(document.records) - 1)
    original = layout.range_bounds(0, 1)
    first = layout.characters[0]
    for scale in (Vec2(-1, 1), Vec2(0, 0)):
        changed = replace(
            first,
            object=replace(
                first.object, state=replace(first.object.state, scale=scale)
            ),
        )
        value = replace(
            layout, characters=(changed, *layout.characters[1:])
        ).range_bounds(0, 1, time=0)
        assert value.width == pytest.approx(original.width * abs(scale.x))
        assert value.height == pytest.approx(original.height * abs(scale.y))
        assert value.left == pytest.approx(
            original.left - (original.width if scale.x < 0 else 0)
        )
