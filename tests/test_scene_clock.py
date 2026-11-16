"""Visibility changes preserve authored state, mask, geometry and paint clocks."""

from dataclasses import replace

import pytest

from kara_templater import (
    RED,
    WHITE,
    Coverage,
    Document,
    FadeIn,
    Glow,
    GlowFunction,
    Lifetime,
    ObjectGroup,
    PathFunction,
    PathObject,
    RectangleClip,
    RectangleFunction,
    Scene,
    SceneBudget,
    SoftSweep,
    StatePatch,
    Tween,
    Vec2,
    VectorPath,
    VisualState,
    echoes,
)
from kara_templater._raster import rasterize


@pytest.mark.parametrize("coverage", (False, True))
def test_cropped_visibility_preserves_all_local_clocks_and_delayed_copy(coverage):
    leaf = PathObject(
        id="shape",
        lifetime=Lifetime(1, 3),
        path=VectorPath.rectangle(30, 20),
        state=VisualState(position=Vec2(20, 20)),
        deform=PathFunction(
            lambda path, time: path.map(lambda p: p + Vec2(0, time)),
            max_points=4,
            breakpoints=(1,),
        ),
        material=SoftSweep(left=20, right=70, start=0, duration=2, fill=(WHITE, RED)),
        clip=RectangleClip(
            0,
            0,
            80,
            60,
            deform=RectangleFunction(lambda t: (0, 0, 40 + 15 * t, 60), (1,)),
        ),
    ).animate(Tween(StatePatch(position=Vec2(30, 20))), duration=2)
    group = ObjectGroup(
        id="root",
        lifetime=leaf.lifetime,
        children=(leaf,),
        coverage=Coverage(
            glows={
                leaf.id: GlowFunction(
                    lambda state, t: Glow(RED, blur=t),
                    max_blur=2,
                    max_border=0,
                    breakpoints=(1,),
                )
            }
        )
        if coverage
        else None,
    ).animate(FadeIn(), duration=2)
    cropped = replace(
        group,
        lifetime=Lifetime(2, 3),
        clock_start=1,
        children=(replace(leaf, lifetime=Lifetime(2, 3), clock_start=1),),
    )
    doc = Document.create(width=100, height=80)
    budget = SceneBudget(fps=10, max_events=100_000, max_active=10_000)
    original_scene = Scene(doc).add(group)
    cropped_scene = Scene(doc).add(cropped)
    original = original_scene.compile(budget=budget).document.dumps()
    output = cropped_scene.compile(budget=budget).document.dumps()
    for ms in (2550, 2050, 2850):
        assert original_scene.evaluator().at(
            leaf.id, ms / 1000
        ) == cropped_scene.evaluator().at(leaf.id, ms / 1000)
        actual = rasterize(output, ms, (100, 80)).rgba
        assert any(actual[3::4])
        assert actual == rasterize(original, ms, (100, 80)).rgba
    assert not any(rasterize(output, 1500, (100, 80)).rgba)
    clone = cropped.copy(id="clone", delay=3)
    assert clone.time_origin == 4
    assert Scene(doc).add(clone).evaluator().at(
        "clone/shape", 5.5
    ) == cropped_scene.evaluator().at("shape", 2.5)


def test_visibility_clock_validation_and_echo_preserve_original_progress():
    node = PathObject(
        id="shape", lifetime=Lifetime(1, 3), path=VectorPath.rectangle(5, 5)
    ).animate(Tween(StatePatch(position=Vec2(20, 0))), duration=2)
    node = replace(node, lifetime=Lifetime(2, 3), clock_start=1)
    assert node.at(2.5).position == Vec2(15, 0)
    echo = echoes(node, count=1, spacing=1, opacity=1)[0]
    assert echo.at(3.5).position == Vec2(15, 0)
    for origin in (-1, 3.1, float("nan")):
        with pytest.raises(ValueError, match="clock|finite"):
            replace(node, clock_start=origin)


def test_native_coverage_opacity_uses_retained_origin():
    leaf = PathObject(
        id="shape", lifetime=Lifetime(1, 3), path=VectorPath.rectangle(10, 10)
    )
    original = ObjectGroup(
        id="root", lifetime=leaf.lifetime, children=(leaf,), coverage=Coverage()
    ).animate(FadeIn(), duration=2)
    cropped = replace(original, lifetime=Lifetime(2, 3), clock_start=1)
    doc = Document.create(width=32, height=32)
    before = Scene(doc).add(original).compile(native_tweens=True)
    after = Scene(doc).add(cropped).compile(native_tweens=True)
    assert after.objects[0].strategy == "coverage-native-opacity"
    for time in (2100, 2500, 2900):
        assert (
            rasterize(before.document.dumps(), time, (32, 32)).rgba
            == rasterize(after.document.dumps(), time, (32, 32)).rgba
        )


def test_offscreen_geometry_and_opacity_preserve_clock_after_visibility_crop():
    from kara_templater import StateFunction, rasterize_group

    leaf = PathObject(
        id="shape", lifetime=Lifetime(1, 3), path=VectorPath.rectangle(10, 10)
    )
    original = ObjectGroup(id="root", lifetime=leaf.lifetime, children=(leaf,)).animate(
        StateFunction(
            lambda state, p: replace(state, position=Vec2(10 * p, 5), opacity=p),
            frozenset(("position", "opacity")),
        ),
        duration=2,
    )
    cropped = replace(original, lifetime=Lifetime(2, 3), clock_start=1)
    budget = SceneBudget(fps=10)
    before = (
        rasterize_group(original, resolution=(32, 32), budget=budget)
        .scene.compile()
        .document.dumps()
    )
    after = (
        rasterize_group(cropped, resolution=(32, 32), budget=budget)
        .scene.compile()
        .document.dumps()
    )
    for time in (2050, 2550, 2850):
        assert (
            rasterize(before, time, (32, 32)).rgba
            == rasterize(after, time, (32, 32)).rgba
        )


@pytest.mark.parametrize("coverage", (False, True))
def test_visibility_before_clock_origin_preserves_signed_callback_time(coverage):
    samples = []

    def geometry(path, time):
        samples.append(time)
        return path.map(lambda point: point + Vec2(2 * time, 0))

    leaf = PathObject(
        id="shape",
        lifetime=Lifetime(1, 3),
        path=VectorPath.rectangle(10, 10),
        state=VisualState(position=Vec2(10, 10)),
        deform=PathFunction(geometry, max_points=4),
    ).animate(Tween(StatePatch(position=Vec2(20, 10))), duration=2)
    original = ObjectGroup(
        id="root",
        lifetime=leaf.lifetime,
        children=(leaf,),
        coverage=Coverage() if coverage else None,
    )
    early = replace(
        original,
        lifetime=Lifetime(0.5, 3),
        clock_start=1,
        children=(replace(leaf, lifetime=Lifetime(0.5, 3), clock_start=1),),
    )
    doc = Document.create(width=48, height=32)
    budget = SceneBudget(fps=10, max_events=100_000)
    normal = Scene(doc).add(original).compile(budget=budget, native_tweens=True)
    samples.clear()
    expanded = Scene(doc).add(early).compile(budget=budget, native_tweens=True)
    assert any(time < 0 for time in samples)
    assert early.children[0].at(0.75) == leaf.state
    assert any(rasterize(expanded.document.dumps(), 750, (48, 32)).rgba[3::4])
    for time in (1050, 1550, 2550):
        assert (
            rasterize(expanded.document.dumps(), time, (48, 32)).rgba
            == rasterize(normal.document.dumps(), time, (48, 32)).rgba
        )
    copied = early.copy(id="delayed", delay=2)
    assert copied.time_origin == copied.children[0].time_origin == 3
    assert copied.children[0].at(2.75) == leaf.state


def test_signed_geometry_and_partition_breakpoints_cannot_precede_scene_zero():
    from kara_templater import CoveragePartition

    shape = PathObject(
        id="shape",
        lifetime=Lifetime(0.5, 2),
        clock_start=1,
        path=VectorPath.rectangle(5, 5),
    )
    with pytest.raises(ValueError, match="geometry breakpoint"):
        replace(shape, deform=PathFunction(lambda path, time: path, 4, (-1.1,)))
    partition = CoveragePartition(
        lambda state, time: (), max_regions=1, breakpoints=(-1.1,)
    )
    group = ObjectGroup(
        id="root",
        lifetime=shape.lifetime,
        children=(shape,),
        coverage=Coverage(partitions={shape.id: partition}),
    )
    with pytest.raises(ValueError, match="partition breakpoint"):
        Scene(Document.create()).add(group).compile()


@pytest.mark.parametrize("coverage", (False, True))
@pytest.mark.parametrize("lead,tail", ((0.1, 0.1), (0.2, 0.2)))
def test_decoration_started_before_zero_keeps_progress_and_body_clock(
    coverage: bool, lead: float, tail: float
) -> None:
    # Body timing is always 0.05..0.5 seconds. Only the decorative margins have
    # independent lead/tail durations; the visible window starts at zero.
    def bounds(time: float) -> tuple[float, float, float, float]:
        if time < 0.05:
            front = 100 * (time - (0.05 - lead)) / lead
        elif time < 0.5:
            front = 100 + 100 * (time - 0.05) / 0.45
        else:
            front = min(300, 200 + 100 * (time - 0.5) / tail)
        return (0, 0, front, 20)

    mask = RectangleClip(
        0,
        0,
        300,
        20,
        deform=RectangleFunction(bounds, (0.05, 0.5, 0.5 + tail)),
    )
    leaf = PathObject(
        id="decorated",
        lifetime=Lifetime(0, 0.8),
        path=VectorPath.rectangle(300, 20),
        clip=mask,
    )
    group = ObjectGroup(
        id="root",
        lifetime=leaf.lifetime,
        children=(leaf,),
        coverage=Coverage() if coverage else None,
    )
    doc = Document.create(width=320, height=32)
    budget = SceneBudget(fps=100, max_events=20_000)
    result = Scene(doc).add(group).compile(budget=budget)
    # Independent expected front positions at 10ms frame midpoints. The body
    # entries are identical despite the different decorative lead/tail lengths.
    expected = {
        0: 55 if lead == 0.1 else 77.5,
        40: 95 if lead == 0.1 else 97.5,
        50: 100 + 100 / 90,
        270: 150,
        490: 200 - 100 / 90,
        500: 205 if tail == 0.1 else 202.5,
        700: 300,
    }
    for time, front in expected.items():
        reference = (
            Scene(doc)
            .add(replace(leaf, clip=RectangleClip(0, 0, front, 20)))
            .compile(budget=budget)
        )
        assert (
            rasterize(result.document.dumps(), time, (320, 32)).rgba
            == rasterize(reference.document.dumps(), time, (320, 32)).rgba
        )
    assert mask.deform is not None
    for time, front in ((0, 50 if lead == 0.1 else 75), (0.05, 100), (0.5, 200)):
        sampled = mask.deform.sample(time)
        assert sampled is not None
        assert sampled[2] == pytest.approx(front)
