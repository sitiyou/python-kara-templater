"""Coverage is an explicit strategy inside the same Scene as ordinary drawings."""

from dataclasses import replace

import pytest

from kara_templater import (
    BLUE,
    RED,
    Coverage,
    Document,
    Glow,
    Lifetime,
    ObjectGroup,
    PathObject,
    Scene,
    SceneBudget,
    SceneCompileError,
    ScopeOpacity,
    Vec2,
    VectorPath,
    VisualState,
)
from kara_templater._raster import rasterize

BUDGET = SceneBudget(fps=10, max_events=20_000, max_active=5_000)


_POSITION = Vec2(5, 5)


def drawing(identity: str, color=RED, position=_POSITION) -> PathObject:
    return PathObject(
        id=identity,
        lifetime=Lifetime(0, 1),
        path=VectorPath.rectangle(20, 20),
        state=VisualState(position=position, fill=color),
    )


def group() -> ObjectGroup:
    return ObjectGroup(
        id="word",
        lifetime=Lifetime(0, 1),
        state=VisualState(opacity=0.5),
        children=(drawing("first"), drawing("second")),
    )


def pixel(result, x=10, y=10):
    frame = rasterize(result.document.dumps(), 500, (64, 48))
    offset = (y * 64 + x) * 4
    return tuple(frame.rgba[offset : offset + 4])


def test_mixed_scene_order_and_composite_alpha_are_explicit():
    doc = Document.create(width=64, height=48)
    background = replace(
        drawing("background", BLUE, Vec2()), path=VectorPath.rectangle(64, 48)
    )
    covered = (
        Scene(doc)
        .add(background, replace(group(), coverage=Coverage()))
        .compile(budget=BUDGET)
    )
    ordinary = Scene(doc).add(background, group()).compile(budget=BUDGET)
    assert [report.id for report in covered.objects] == ["background", "word"]
    assert covered.objects[1].strategy == "coverage"
    assert all(report.strategy != "native-event" for report in covered.objects)
    assert all(not event.comment for event in covered.document.lines)
    r, g, b, a = pixel(covered)
    assert (r, g, b, a) == pytest.approx((128, 0, 127, 255), abs=1)
    assert pixel(ordinary)[0] > r + 50
    foreground = drawing("foreground", BLUE)
    overlaid = (
        Scene(doc)
        .add(background, replace(group(), coverage=Coverage()), foreground)
        .compile(budget=BUDGET)
    )
    assert pixel(overlaid) == (0, 0, 255, 255)


def test_copy_retargets_material_and_scope_ownership():
    root = replace(
        group(),
        coverage=Coverage(
            glows={"first": Glow(color=RED, blur=1)},
            scope_opacities={"first": (ScopeOpacity("word", lambda t: 1),)},
        ),
    )
    clone = root.copy(id="copy", delay=1)
    assert clone.coverage is not None
    assert tuple(clone.coverage.glows) == ("copy/first",)
    assert clone.coverage.scope_opacities["copy/first"][0].owner == "copy"
    scene = Scene(Document.create(width=64, height=48)).add(root, clone)
    result = scene.compile(budget=BUDGET)
    assert [report.id for report in result.objects] == ["word", "copy"]
    assert result.objects[1].sample_times[0] == 1.05
    assert rasterize(result.document.dumps(), 500, (64, 48)) == rasterize(
        result.document.dumps(), 1500, (64, 48)
    )


def test_nested_composition_is_rejected_instead_of_silently_changing_scopes():
    inner = replace(group(), coverage=Coverage())
    outer = ObjectGroup(id="outer", lifetime=Lifetime(0, 1), children=(inner,))
    with pytest.raises(SceneCompileError, match="nested coverage"):
        Scene(Document.create()).add(replace(outer, coverage=Coverage())).compile()


def test_mixed_scene_enforces_one_output_budget():
    doc = Document.create(width=64, height=48)
    scene = Scene(doc).add(drawing("ordinary"), replace(group(), coverage=Coverage()))
    with pytest.raises(SceneCompileError, match="budget"):
        scene.compile(budget=replace(BUDGET, max_events=1))


def test_coverage_in_parent_keeps_lifetime_mask_and_composite_opacity():
    from kara_templater import RectangleClip

    inner = replace(group(), coverage=Coverage())
    outer = ObjectGroup(
        id="parent",
        lifetime=Lifetime(0.2, 0.8),
        children=(inner,),
        state=VisualState(position=Vec2(10, 5), opacity=0.5),
        clip=RectangleClip(0, 0, 25, 48),
    )
    result = (
        Scene(Document.create(width=64, height=48)).add(outer).compile(budget=BUDGET)
    )
    assert result.objects[0].id == "word"
    assert result.objects[0].sample_times == pytest.approx(
        (0.25, 0.35, 0.45, 0.55, 0.65, 0.75)
    )
    assert pixel(result, 20, 15) == pytest.approx((255, 0, 0, 64), abs=1)
    assert pixel(result, 30, 15)[3] == 0
    assert all(
        200 <= event.start_time < event.end_time <= 800
        for event in result.document.lines
    )
    # Cropping the output lifetime must not retime any node's own clock.
    from kara_templater import FadeIn

    moving = replace(inner, animations=()).animate(FadeIn(), at=0, duration=1)
    result = (
        Scene(Document.create(width=64, height=48))
        .add(replace(outer, children=(moving,), clip=None))
        .compile(budget=BUDGET)
    )
    assert pixel(result, 20, 15)[3] == pytest.approx(255 * 0.5 * 0.5 * 0.55, abs=2)


def test_coverage_external_reference_uses_shared_scene_context():
    from kara_templater import FollowObject

    anchor = replace(
        drawing("anchor", BLUE, Vec2(30, 10)), path=VectorPath.rectangle(1, 1)
    )
    follower = replace(
        drawing("follower"), reference=FollowObject("anchor", offset=Vec2(5, 5))
    )
    covered = ObjectGroup(
        id="covered", lifetime=Lifetime(0, 1), children=(follower,), coverage=Coverage()
    )
    doc = Document.create(width=64, height=48)
    scene = Scene(doc).add(covered, anchor)
    result = scene.compile(budget=BUDGET)
    assert pixel(result, 40, 20) == (255, 0, 0, 255)
    assert pixel(result, 10, 10)[3] == 0
    assert scene.compile(budget=BUDGET).document.dumps() == result.document.dumps()


def test_parent_siblings_do_not_get_composited_into_coverage_branch():
    inner = replace(group(), coverage=Coverage())
    blue = drawing("blue", BLUE)
    parent = ObjectGroup(
        id="parent",
        lifetime=Lifetime(0, 1),
        children=(inner, blue),
        state=VisualState(opacity=0.5),
    )
    result = (
        Scene(Document.create(width=64, height=48)).add(parent).compile(budget=BUDGET)
    )
    assert [report.id for report in result.objects] == ["word", "blue"]
    # Parent opacity applies to each emitted child; blue overlays quarter-alpha red.
    assert pixel(result)[3] == pytest.approx(159, abs=2)
    assert pixel(result)[2] > pixel(result)[0]
    invisible = replace(parent, lifetime=Lifetime(2, 3))
    assert (
        Scene(Document.create(width=64, height=48))
        .add(invisible)
        .compile(budget=BUDGET)
        .event_count
        == 0
    )


def test_parent_window_skips_inactive_materials_without_invoking_callbacks():
    from kara_templater import GlowFunction

    def forbidden(state, seconds):
        pytest.fail("a hidden descendant must not evaluate glow callbacks")

    late = replace(drawing("late"), lifetime=Lifetime(1, 2))
    inner = ObjectGroup(
        id="covered",
        lifetime=Lifetime(0, 2),
        children=(drawing("visible"), late),
        coverage=Coverage(
            glows={"late": GlowFunction(forbidden, max_blur=2, max_border=0)}
        ),
    )
    parent = ObjectGroup(id="parent", lifetime=Lifetime(0, 0.8), children=(inner,))
    result = (
        Scene(Document.create(width=64, height=48)).add(parent).compile(budget=BUDGET)
    )
    assert pixel(result) == (255, 0, 0, 255)


@pytest.mark.parametrize("sampled", (False, True))
def test_scene_order_is_independent_of_identity_and_exposure_start(sampled):
    from kara_templater import AnimationClip, StateFunction

    earlier = replace(drawing("z", BLUE), lifetime=Lifetime(0, 1))
    later = replace(drawing("a", RED), lifetime=Lifetime(0.4, 0.8))
    if sampled:
        earlier = replace(
            earlier,
            animations=(AnimationClip(0, 1, StateFunction(lambda state, p: state)),),
        )
        later = replace(
            later,
            animations=(AnimationClip(0, 0.4, StateFunction(lambda state, p: state)),),
        )
    doc = Document.create(width=64, height=48)
    scene = Scene(doc).add(earlier, later)
    result = scene.compile(budget=BUDGET)
    assert [report.id for report in result.objects] == ["z", "a"]
    assert pixel(result) == (255, 0, 0, 255)
    for time in (100, 900):
        frame = rasterize(result.document.dumps(), time, (64, 48)).rgba
        offset = (10 * 64 + 10) * 4
        assert tuple(frame[offset : offset + 4]) == (0, 0, 255, 255)
    reversed_result = Scene(doc).add(later, earlier).compile(budget=BUDGET)
    assert pixel(reversed_result) == (0, 0, 255, 255)
