"""Known line alpha lowers after composition through the common Scene compiler."""

from dataclasses import replace

import pytest
from test_lyric_coverage import BUDGET, source, track

from kara_templater import (
    FadeIn,
    FadeOut,
    GlowFunction,
    ObjectGroup,
    RasterSettings,
    SceneCompileError,
    StateFunction,
    StatePatch,
    Timeline,
    Tween,
    prepare_tracks,
)
from kara_templater._raster import rasterize


def subject():
    document = source()
    document.lines[0].text = r"{\k20}A|a"
    scene = prepare_tracks(document, tracks=(track(),))
    return scene


@pytest.mark.parametrize("delay", (0, 1.03, 1234.56))
def test_native_line_fade_reduces_output_and_matches_independent_alpha(delay):
    scene = subject()
    line = scene.lines[0].copy(id="shifted", delay=delay)
    scene.objects[0] = line
    full = scene.compile(budget=BUDGET).document.dumps()
    scene.objects[0] = line.animate(FadeIn(), duration=0.4)
    native = scene.compile(budget=BUDGET, native_tweens=True)
    sampled = scene.compile(budget=BUDGET)
    assert native.objects[0].strategy == "coverage-native-opacity"
    assert native.event_count < sampled.event_count
    assert any(r"\t(" in event.text for event, _ in native.event_origins)
    # Compare against unfaded actual geometry at arbitrary seeks, not merely
    # the compiler's held-sample centers. The expected alpha is independent.
    for time in (390, 0, 150, 80, 250, 350):
        before = rasterize(full, round(delay * 1000) + time, (160, 100)).rgba
        after = rasterize(
            native.document.dumps(), round(delay * 1000) + time, (160, 100)
        ).rgba
        for index in range(0, len(before), 4):
            assert after[index + 3] == pytest.approx(
                before[index + 3] * time / 400, abs=1
            )
            if after[index + 3]:
                assert after[index : index + 3] == before[index : index + 3]
    assert (
        scene.compile(budget=BUDGET, native_tweens=True).document.dumps()
        == native.document.dumps()
    )


def test_common_timeline_retains_piecewise_alpha_and_base_opacity():
    scene = subject()
    line = scene.lines[0]
    line = replace(line, state=replace(line.state, opacity=0.6))
    timeline = Timeline()
    timeline.play(FadeIn(), duration=0.1)
    timeline.wait(0.1)
    timeline.play(FadeOut(), duration=0.2)
    scene.objects[0] = line.animate(timeline.animation, duration=0.4)
    native = scene.compile(budget=BUDGET, native_tweens=True)
    assert native.objects[0].strategy == "coverage-native-opacity"
    scene.objects[0] = replace(line, state=replace(line.state, opacity=1))
    full = scene.compile(budget=BUDGET).document.dumps()
    for time, opacity in ((50, 0.3), (150, 0.6), (250, 0.45), (350, 0.15)):
        before = rasterize(full, time, (160, 100)).rgba
        after = rasterize(native.document.dumps(), time, (160, 100)).rgba
        assert max(after[3::4]) == pytest.approx(max(before[3::4]) * opacity, abs=1)


@pytest.mark.parametrize("kind", ("callback", "jump", "release", "parent"))
@pytest.mark.parametrize("delay", (0, 1234.56))
def test_unproven_opacity_keeps_sampled_semantics(kind, delay):
    scene = subject()
    line = scene.lines[0].copy(id="shifted", delay=delay)
    if kind == "callback":
        animation = StateFunction(
            lambda base, p: replace(base, opacity=p * p), frozenset(("opacity",))
        )
    else:
        animation = FadeIn() if kind == "jump" else Tween(StatePatch(opacity=0.2))
    line = line.animate(
        animation, duration=0.2, at=0.1 if kind == "jump" else 0, hold=kind != "release"
    )
    scene.objects[0] = (
        ObjectGroup(id="parent", lifetime=line.lifetime, children=(line,))
        if kind == "parent"
        else line
    )
    sampled = scene.compile(budget=BUDGET)
    native = scene.compile(budget=BUDGET, native_tweens=True)
    assert native.objects[0].strategy == "coverage"
    assert native.document.dumps() == sampled.document.dumps()


@pytest.mark.parametrize("limit", ("max_frame_chars", "max_output_chars"))
def test_character_budgets_count_native_alpha_tags(limit):
    scene = subject()
    line = scene.lines[0]
    plain = scene.compile(budget=BUDGET)
    scene.objects[0] = line.animate(FadeIn(), duration=0.4)
    native = scene.compile(budget=BUDGET, native_tweens=True)

    def peak(result):
        return max(
            sum(
                len(event.text)
                for event, _ in result.event_origins
                if event.start_time <= time < event.end_time
            )
            for time in (0, 100, 200, 300)
        )

    def cost(result):
        return (
            peak(result)
            if limit == "max_frame_chars"
            else sum(len(event.text) for event, _ in result.event_origins)
        )

    assert cost(native) > cost(plain)
    assert line.coverage is not None
    scene.objects[0] = replace(
        scene.objects[0],
        coverage=replace(
            line.coverage, settings=RasterSettings(**{limit: cost(plain)})
        ),
    )
    with pytest.raises(SceneCompileError, match="budget.*opacity"):
        scene.compile(budget=BUDGET, native_tweens=True)


def test_material_callbacks_observe_original_opacity_during_native_lowering():
    scene = subject()
    line = scene.lines[0].animate(FadeIn(), duration=0.4)
    assert line.coverage is not None
    seen = []

    def inspect(state, time):
        seen.append((time, state.opacity))
        return None

    scene.objects[0] = replace(
        line,
        coverage=replace(
            line.coverage,
            glows={
                target.node_id: GlowFunction(inspect, max_blur=0, max_border=0)
                for target in line.query("character")
            },
        ),
    )
    result = scene.compile(budget=BUDGET, native_tweens=True)
    assert result.objects[0].strategy == "coverage-native-opacity"
    assert seen
    assert all(opacity == pytest.approx(time / 0.4) for time, opacity in seen)
