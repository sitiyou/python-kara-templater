"""Native clip subdivision preserves geometry clocks and bounded edge error."""

import re
from dataclasses import replace

import pytest

from kara_templater import (
    Document,
    EventOrigin,
    FadeIn,
    FadeOut,
    Lifetime,
    ObjectGroup,
    PathObject,
    RectangleClip,
    RectangleKeyframes,
    ScalePulse,
    Scene,
    SceneBudget,
    SceneCompileError,
    SourceRef,
    Vec2,
    VectorPath,
    VisualState,
    linear_rate,
)
from kara_templater._raster import rasterize


def subject(fade: bool = False, pivot_x: float = 0) -> PathObject:
    node = PathObject(
        id="pulse",
        lifetime=Lifetime(0, 2.5),
        path=VectorPath.rectangle(100, 20),
        state=VisualState(position=Vec2(50, 30)),
        origin=EventOrigin((SourceRef("lyric", 0),), "native sweep"),
        clip=RectangleClip(
            0,
            -100,
            100,
            100,
            space="local",
            deform=RectangleKeyframes(
                (
                    (0, (0, -100, 0, 100)),
                    (1, (0, -100, 0, 100)),
                    (2, (0, -100, 100, 100)),
                )
            ),
        ),
    ).animate(
        ScalePulse(pivot=Vec2(pivot_x, 10), peak=2, rate=linear_rate),
        at=1, duration=1,
    )
    return (
        node.animate(FadeIn(), duration=2).animate(FadeOut(), at=2, duration=0.5)
        if fade
        else node
    )


@pytest.mark.parametrize("pivot_x", (0, 50))
@pytest.mark.parametrize("fade", (False, True))
@pytest.mark.parametrize("crop", (False, True))
def test_native_motion_bounds_error_keeps_original_clocks_and_matches_static_pixels(
    fade, crop, pivot_x
):
    node = subject(fade, pivot_x)
    if crop:
        node = replace(node, lifetime=Lifetime(1.25, 2.5), clock_start=0)
    doc = Document.create(width=300, height=100)
    budget = SceneBudget(clip_error_px=0.75)
    result = Scene(doc).add(node).ass.compile(native_tweens=True, budget=budget)
    assert result.objects[0].strategy == "native-clip"
    assert 4 < result.event_count < 30
    for event in result.document.lines:
        if not 1000 <= event.start_time < 2000:
            continue
        clips = re.findall(r"\\clip\((-?\d+),(-?\d+),(-?\d+),(-?\d+)\)", event.text)
        first, last = [tuple(map(int, match)) for match in (clips[0], clips[-1])]
        for step in range(101):
            p = step / 100
            t = (event.start_time + p * (event.end_time - event.start_time)) / 1000
            scale = 1 + 2 * min(t - 1, 2 - t)
            expected = 50 + (1 - scale) * pivot_x + 100 * (t - 1) * scale
            actual = first[2] + (last[2] - first[2]) * p
            assert abs(actual - expected) <= 0.75 + 1e-8
        # Each subdivision retains the original clock of every intersecting phase.
        transforms = re.findall(r"\\t\((-?\d+),(-?\d+),\\fscx(\d+)", event.text)
        assert [
            (event.start_time + int(a), event.start_time + int(b), int(s))
            for a, b, s in transforms
        ] == [
            phase
            for phase in ((1000, 1500, 200), (1500, 2000, 100))
            if phase[1] > event.start_time and phase[0] < event.end_time
        ]
        if fade:
            match = re.search(r"\\t\((-?\d+),(-?\d+),\\alpha&H00&", event.text)
            assert match and event.start_time + int(match[1]) == 0
            assert event.start_time + int(match[2]) == 2000
        t = event.start_time / 1000
        scale = 1 + 2 * min(t - 1, 2 - t)
        left = 50 + (1 - scale) * pivot_x
        front = left + 100 * (t - 1) * scale
        reference = (
            Scene(doc)
            .add(
                replace(
                    node,
                    animations=(),
                    state=VisualState(
                        position=Vec2(left, 40 - 10 * scale),
                        scale=Vec2(scale, scale),
                        opacity=t / 2 if fade else 1,
                    ),
                    clip=RectangleClip(left, -500, front, 500)
                    if front > left
                    else RectangleClip(0, 0, 1, 1),
                )
            )
            .ass.compile()
        )
        actual_alpha = rasterize(
            result.document.dumps(), round(event.start_time), (300, 100)
        ).rgba[3::4]
        expected_alpha = rasterize(
            reference.document.dumps(), round(event.start_time), (300, 100)
        ).rgba[3::4]
        assert max(
            abs(a - b) for a, b in zip(actual_alpha, expected_alpha, strict=True)
        ) <= (1 if fade else 0)


def test_native_subdivision_enforces_event_and_spatial_limits_with_origin():
    node = subject()
    scene = Scene(Document.create(width=300, height=100)).add(node)
    with pytest.raises(SceneCompileError, match="event budget") as caught:
        scene.ass.compile(native_tweens=True, budget=SceneBudget(max_events=2))
    assert caught.value.origin is node.origin
    with pytest.raises(SceneCompileError, match="ASS time resolution") as caught:
        scene.ass.compile(native_tweens=True, budget=SceneBudget(clip_error_px=0.01))
    assert caught.value.object_id == node.id
    assert caught.value.origin is node.origin


def test_asymmetric_pulse_uses_actual_peak_clock_and_unknown_easing_samples():
    node = replace(subject(), animations=()).animate(
        ScalePulse(peak=2, peak_at=0.3, rate=linear_rate), at=1, duration=1,
    )
    doc = Document.create(width=300, height=100)
    result = Scene(doc).add(node).ass.compile(native_tweens=True)
    assert result.objects[0].strategy == "native-clip"
    phases = set()
    for event in result.document.lines:
        for a, b, scale in re.findall(
            r"\\t\((-?\d+),(-?\d+),\\fscx(\d+)", event.text
        ):
            phases.add((event.start_time + int(a), event.start_time + int(b), int(scale)))
    assert (1000, 1300, 200) in phases
    assert (1300, 2000, 100) in phases
    eased = replace(node, animations=()).animate(
        ScalePulse(peak=2, peak_at=0.3, rate=lambda p: p * p), at=1, duration=1,
    )
    with pytest.raises(SceneCompileError, match="frame sampling"):
        Scene(doc).add(eased).ass.compile(native_tweens=True)


@pytest.mark.parametrize("error", (0, -1, float("nan"), float("inf")))
def test_clip_error_budget_is_finite_and_positive(error):
    with pytest.raises(ValueError):
        SceneBudget(clip_error_px=error)


@pytest.mark.parametrize("nested", (False, True))
def test_linear_translation_and_scale_use_the_same_curve_lowering(nested):
    from kara_templater import StatePatch, Timeline, Tween

    motion = Tween(StatePatch(position=Vec2(70, 20), scale=Vec2(2, 1.5)))
    animation = Timeline().play(motion, duration=1).animation if nested else motion
    node = replace(subject(), animations=()).animate(animation, at=1, duration=1)
    doc = Document.create(width=300, height=100)
    result = Scene(doc).add(node).ass.compile(native_tweens=True)
    assert result.objects[0].strategy == "native-clip"
    for time in (1000, 1500, 2000):
        p = (time - 1000) / 1000
        position, scale = Vec2(50 + 20 * p, 30 - 10 * p), Vec2(1 + p, 1 + p / 2)
        reference = Scene(doc)
        if p:
            reference.add(
                replace(
                    node,
                    animations=(),
                    state=VisualState(position=position, scale=scale),
                    clip=RectangleClip(
                        position.x, -500, position.x + 100 * p * scale.x, 500
                    ),
                )
            )
        expected = reference.ass.compile()
        assert (
            rasterize(result.document.dumps(), time, (300, 100)).rgba
            == rasterize(expected.document.dumps(), time, (300, 100)).rgba
        )


def test_short_parent_exposures_preserve_scale_fade_and_clip_clocks():
    node = subject(fade=True, pivot_x=50)
    doc = Document.create(width=300, height=100)
    whole = Scene(doc).add(node).ass.compile(native_tweens=True).document.dumps()
    for start in range(1000, 2480, 40):
        group = ObjectGroup(
            id="exposure",
            lifetime=Lifetime(start / 1000, (start + 40) / 1000),
            children=(node,),
        )
        cropped = Scene(doc).add(group).ass.compile(native_tweens=True)
        assert cropped.objects[0].strategy == "native-clip"
        for time in (start, start + 20):
            assert (
                rasterize(cropped.document.dumps(), time, (300, 100)).rgba
                == rasterize(whole, time, (300, 100)).rgba
            )


@pytest.mark.parametrize("crop", (False, True))
def test_parent_fade_and_child_pulse_use_distinct_original_clocks(crop):
    child = replace(
        subject(pivot_x=50),
        lifetime=Lifetime(0.5, 3),
        clock_start=0.5,
        state=VisualState(position=Vec2(50, 30), opacity=0.6),
    )
    parent = (
        ObjectGroup(
            id="line",
            lifetime=Lifetime(0, 3),
            children=(child,),
            state=VisualState(opacity=0.5),
        )
        .animate(FadeIn(), duration=2)
        .animate(FadeOut(), at=2, duration=1)
    )
    if crop:
        parent = replace(parent, lifetime=Lifetime(1.75, 3), clock_start=0)
    doc = Document.create(width=300, height=100)
    result = (
        Scene(doc).add(parent).ass.compile(native_tweens=True, budget=SceneBudget())
    )
    assert result.objects[0].strategy == "native-clip"
    assert result.event_count < 30
    for event in result.document.lines:
        time = round(event.start_time)
        t = time / 1000
        local = t - 0.5
        scale = 1 + 2 * max(0, min(local - 1, 2 - local))
        left = 50 + (1 - scale) * 50
        front = left + 100 * max(0, min(1, local - 1)) * scale
        opacity = 0.3 * (t / 2 if t < 2 else 3 - t)
        reference = Scene(doc)
        if front > left:
            reference.add(
                replace(
                    child,
                    animations=(),
                    state=VisualState(
                        position=Vec2(left, 40 - 10 * scale),
                        scale=Vec2(scale, scale),
                        opacity=opacity,
                    ),
                    clip=RectangleClip(left, -500, front, 500),
                )
            )
        actual = rasterize(result.document.dumps(), time, (300, 100)).rgba[3::4]
        expected = rasterize(
            reference.ass.compile().document.dumps(), time, (300, 100)
        ).rgba[3::4]
        assert max(abs(a - b) for a, b in zip(actual, expected, strict=True)) <= 1


def test_overlapping_inherited_opacity_curves_remain_sampled():
    child = subject(fade=True)
    parent = ObjectGroup(
        id="parent",
        lifetime=child.lifetime,
        children=(child,),
    ).animate(FadeIn(), duration=2)
    with pytest.raises(SceneCompileError, match="frame sampling"):
        Scene(Document.create(width=300, height=100)).add(parent).ass.compile()


def test_native_decoration_channels_keep_original_clocks_through_clip_cuts():
    from kara_templater import StatePatch, Tween

    node = subject()
    node = replace(node, state=replace(node.state, border=3, blur=8))
    node = node.animate(Tween(StatePatch(border=6, blur=16)), at=1, duration=0.5)
    node = node.animate(Tween(StatePatch(border=3, blur=8)), at=1.5, duration=0.5)
    doc = Document.create(width=300, height=100)
    result = Scene(doc).add(node).ass.compile(native_tweens=True)
    for event in result.document.lines:
        if 1000 <= event.start_time < 1500:
            match = re.search(r"\\t\((-?\d+),(-?\d+),\\bord6\\blur16", event.text)
            assert match
            assert event.start_time + int(match[1]) == 1000
            assert event.start_time + int(match[2]) == 1500
            assert r"\bord3\blur8" in event.text
    for time, scale in ((1250, 1.5), (1500, 2), (1750, 1.5)):
        reference = (
            Scene(doc)
            .add(
                replace(
                    node,
                    animations=(),
                    state=VisualState(
                        position=Vec2(50, 40 - 10 * scale),
                        scale=Vec2(scale, scale),
                        border=3 * scale,
                        blur=8 * scale,
                    ),
                    clip=RectangleClip(
                        50, -500, 50 + 100 * (time / 1000 - 1) * scale, 500
                    ),
                )
            )
            .ass.compile()
        )
        assert (
            rasterize(result.document.dumps(), time, (300, 100)).rgba
            == rasterize(reference.document.dumps(), time, (300, 100)).rgba
        )
