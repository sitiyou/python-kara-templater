"""Concrete scene extension contracts, independent of internal implementation."""

from dataclasses import replace
from typing import assert_type

from kara_templater import (
    Affine2D,
    Document,
    Lifetime,
    ObjectGroup,
    ObjectReport,
    RasterizedGroup,
    Scene,
    SceneResult,
    SceneTimeline,
    StateFunction,
    StateKeyframe,
    StatePatch,
    TextObject,
    Tween,
    Vec2,
    VisualState,
)


def wave(state: VisualState, progress: float) -> VisualState:
    return replace(state, position=state.position + Vec2(progress, 0))


def author(document: Document) -> SceneResult:
    timeline = SceneTimeline().play(Tween(StatePatch(opacity=0.5)), duration=1)
    assert_type(
        timeline.play(
            StateFunction(wave, frozenset(("position",))),
            duration=1,
            breakpoints=(0.35,),
        ),
        SceneTimeline,
    )
    node = TextObject(
        id="word", text="typed", lifetime=Lifetime(0, 2), animations=timeline.clips
    )
    assert_type(node.at(0.5), VisualState)
    assert_type(node.copy(id="copy"), TextObject)
    assert_type(
        SceneTimeline().keyframes(StateKeyframe(1, StatePatch(opacity=0))),
        SceneTimeline,
    )
    result = Scene(document).add(node).compile()
    assert_type(result.document, Document)
    assert_type(result.objects, tuple[ObjectReport, ...])
    return result


def affine_contract(state: VisualState) -> Vec2:
    assert_type(state.transform, Affine2D)
    assert_type(state.singular, bool)
    matrix = Affine2D(a=2, d=0.8) @ state.transform
    assert_type(matrix, Affine2D)
    return matrix.apply(Vec2(10, 20))


def raster_contract(group: "ObjectGroup") -> "RasterizedGroup":
    from kara_templater import rasterize_group

    result = rasterize_group(group, resolution=(320, 180), blur_radius=2)
    assert_type(result.scene, Scene)
    assert_type(result.sampled_frames, int)
    return result


assert_type(Scene(Document.create()).compile(native_tweens=True), SceneResult)
