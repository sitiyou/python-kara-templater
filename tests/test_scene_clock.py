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
    SoftSweep,
    StatePatch,
    Tween,
    Vec2,
    VectorPath,
    VisualState,
    echoes,
)


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
    original_scene = Scene(doc).add(group)
    cropped_scene = Scene(doc).add(cropped)
    for time in (2, 2.5, 2.9):
        assert original_scene.evaluator().at(leaf.id, time) == cropped_scene.evaluator().at(leaf.id, time)
    clone = cropped.copy(id="clone", delay=3)
    assert clone.time_origin == 4


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
    assert early.children[0].at(0.75) == leaf.state
    copied = early.copy(id="delayed", delay=2)
    assert copied.time_origin == copied.children[0].time_origin == 3
    assert copied.children[0].at(2.75) == leaf.state


def test_signed_geometry_and_partition_breakpoints_cannot_precede_scene_zero():

    shape = PathObject(
        id="shape",
        lifetime=Lifetime(0.5, 2),
        clock_start=1,
        path=VectorPath.rectangle(5, 5),
    )
    with pytest.raises(ValueError, match="geometry breakpoint"):
        replace(shape, deform=PathFunction(lambda path, time: path, 4, (-1.1,)))


@pytest.mark.parametrize("lead,tail", ((0.1, 0.1), (0.2, 0.2)))
def test_decoration_started_before_zero_keeps_progress_and_body_clock(
    lead: float, tail: float
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
    assert mask.deform is not None
    for time, front in ((0, 50 if lead == 0.1 else 75), (0.05, 100), (0.5, 200)):
        sampled = mask.deform.sample(time)
        assert sampled is not None
        assert sampled[2] == pytest.approx(front)
