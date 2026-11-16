"""A shared preflight can stop ordinary and coverage output before sampling."""

from dataclasses import FrozenInstanceError, replace

import pytest
from test_lyric_coverage import BUDGET, source, track

from kara_templater import (
    GlowFunction,
    Lifetime,
    LyricRule,
    PathObject,
    SceneCompileError,
    SceneEstimate,
    StatePatch,
    Tween,
    Vec2,
    VectorPath,
    prepare_tracks,
)


def subject(calls):
    animation = Tween(
        StatePatch(scale=Vec2(1.2, 1.2)), rate=lambda p: calls.append(p) or p
    )
    document = source()
    scene = prepare_tracks(
        document,
        tracks=(track(animations=(LyricRule("character", "singing", animation),)),),
    )
    scene.add(
        PathObject(
            id="ordinary", lifetime=Lifetime(0, 0.4), path=VectorPath.rectangle(5, 5)
        ).animate(animation, duration=0.4)
    )
    return document, scene


def test_cancel_before_any_frame_callback_without_mutating_sources():
    calls = []
    document, scene = subject(calls)
    original = document.dumps()
    nodes = tuple(scene.objects)
    received = []

    def cancel(estimate: SceneEstimate) -> None:
        assert not calls
        assert estimate.estimated_events > 0
        assert len(estimate.coverage) == 1
        item = estimate.coverage[0]
        assert item.id == scene.lines[0].id
        assert item.frames == 4
        assert item.target_samples >= item.frames
        assert item.max_channel_error == 0
        received.append(estimate)
        raise RuntimeError("cancel expensive render")

    with pytest.raises(RuntimeError, match="cancel expensive render"):
        scene.compile(budget=BUDGET, on_estimate=cancel)
    assert len(received) == 1
    assert not calls
    assert document.dumps() == original
    assert tuple(scene.objects) == nodes
    for field in ("estimated_events", "coverage"):
        with pytest.raises(FrozenInstanceError):
            setattr(received[0], field, 0)


def test_preflight_boundaries_match_actual_grid_and_success_is_repeatable():
    calls = []
    _, scene = subject(calls)
    line = scene.lines[0]
    assert line.coverage is not None
    scene.objects[0] = replace(
        line,
        coverage=replace(
            line.coverage,
            glows={
                target.node_id: GlowFunction(
                    lambda state, t: None, max_blur=0, max_border=0, breakpoints=(0.03,)
                )
                for target in line.query("character")
            },
        ),
    )
    estimates = []
    first = scene.compile(budget=BUDGET, on_estimate=estimates.append)
    assert calls
    second = scene.compile(budget=BUDGET, on_estimate=estimates.append)
    assert estimates[0] == estimates[1]
    assert estimates[0].coverage[0].frames == 5
    report = next(item for item in first.objects if item.id == line.id)
    assert estimates[0].coverage[0].frames == len(report.sample_times)
    assert first.document.dumps() == second.document.dumps()


def test_all_coverage_preflight_finishes_before_ordinary_sampling_or_estimate():
    from kara_templater import RasterSettings

    calls = []
    _, scene = subject(calls)
    line = scene.lines[0]
    assert line.coverage is not None
    scene.objects[0] = replace(
        line, coverage=replace(line.coverage, settings=RasterSettings(max_frames=1))
    )
    estimates = []
    with pytest.raises(SceneCompileError, match="frame budget"):
        scene.compile(budget=BUDGET, on_estimate=estimates.append)
    assert not calls
    assert not estimates
