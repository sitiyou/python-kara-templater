"""Concrete scene extension contracts, independent of internal implementation."""

from dataclasses import replace
from typing import assert_type

from kara_templater import (
    Affine2D,
    CoverageEstimate,
    Document,
    Lifetime,
    ObjectReport,
    ScalePulse,
    Scene,
    SceneEstimate,
    SceneResult,
    StateFunction,
    StateKeyframe,
    StatePatch,
    TextObject,
    Timeline,
    Tween,
    Vec2,
    VisualState,
)


def wave(state: VisualState, progress: float) -> VisualState:
    return replace(state, position=state.position + Vec2(progress, 0))


def author(document: Document) -> SceneResult:
    timeline = Timeline().play(Tween(StatePatch(opacity=0.5)), duration=1)
    assert_type(
        timeline.play(
            StateFunction(wave, frozenset(("position",))),
            duration=1,
            breakpoints=(0.35,),
        ),
        Timeline,
    )
    node = TextObject(
        id="word", text="typed", lifetime=Lifetime(0, 2), animations=timeline.clips
    )
    assert_type(node.at(0.5), VisualState)
    assert_type(node.copy(id="copy"), TextObject)
    assert_type(
        Timeline().keyframes(StateKeyframe(1, StatePatch(opacity=0))),
        Timeline,
    )
    result = Scene(document).add(node).compile()
    assert_type(result.document, Document)
    assert_type(result.objects, tuple[ObjectReport, ...])
    return result


def affine_contract(state: VisualState) -> Vec2:
    assert_type(ScalePulse(pivot=Vec2(10, 20)).sample(state, 0.5), VisualState)
    assert_type(state.transform, Affine2D)
    assert_type(state.singular, bool)
    matrix = Affine2D(a=2, d=0.8) @ state.transform
    assert_type(matrix, Affine2D)
    return matrix.apply(Vec2(10, 20))


assert_type(Scene(Document.create()).compile(native_tweens=True), SceneResult)


def inspect_cost(estimate: SceneEstimate) -> None:
    assert_type(estimate.estimated_events, int)
    assert_type(estimate.coverage, tuple[CoverageEstimate, ...])
    for group in estimate.coverage:
        assert_type(group.frames, int)
        assert_type(group.target_samples, int)
        assert_type(group.max_channel_error, int)


assert_type(Scene(Document.create()).compile(on_estimate=inspect_cost), SceneResult)


def explicit_clock(node: TextObject) -> float:
    from dataclasses import replace

    return replace(node, clock_start=0.0).time_origin
