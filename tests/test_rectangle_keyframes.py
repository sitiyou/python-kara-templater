"""Known rectangle curves share the mask evaluator with arbitrary callbacks."""

from dataclasses import replace

import pytest

from kara_templater import (
    Coverage,
    Document,
    Lifetime,
    ObjectGroup,
    PathObject,
    RectangleClip,
    RectangleKeyframes,
    Scene,
    SceneBudget,
    VectorPath,
)
from kara_templater._raster import rasterize


def curve():
    return RectangleKeyframes(
        (
            (0, (0, 0, 0, 12)),
            (0.2, (0, 0, 8, 12)),
            (0.4, (0, 0, 8, 12)),
            (0.4, (0, 0, 2, 12)),
            (0.6, (0, 0, 12, 12)),
        )
    )


def test_known_curve_holds_pauses_resets_and_preserves_empty_coordinates():
    mask = curve()
    assert mask.bounds_at(-1) == (0, 0, 0, 12)
    assert mask.sample(0) is None
    assert mask.sample(0.1) == (0, 0, 4, 12)
    assert mask.sample(0.3) == (0, 0, 8, 12)
    assert mask.bounds_at(0.4, before=True) == (0, 0, 8, 12)
    assert mask.sample(0.4) == (0, 0, 2, 12)
    assert mask.sample(0.5) == pytest.approx((0, 0, 7, 12))
    assert mask.sample(2) == (0, 0, 12, 12)
    assert mask.breakpoints == (0, 0.2, 0.4, 0.6)


@pytest.mark.parametrize("coverage", (False, True))
@pytest.mark.parametrize("inverse", (False, True))
def test_known_curve_uses_common_sampling_and_keeps_clock_after_crop(coverage, inverse):
    doc = Document.create(width=32, height=32)
    leaf = PathObject(
        id="masked",
        lifetime=Lifetime(1.1, 1.8),
        clock_start=1,
        path=VectorPath.rectangle(16, 12),
        clip=RectangleClip(0, 0, 16, 12, inverse=inverse, deform=curve()),
    )
    group = ObjectGroup(
        id="root",
        lifetime=leaf.lifetime,
        children=(leaf,),
        coverage=Coverage() if coverage else None,
    )
    budget = SceneBudget(fps=10)
    result = Scene(doc).add(group).compile(budget=budget)
    # 100ms midpoint samples; plateau/reset/held tail have independent expected bounds.
    for time, front in ((1100, 6), (1200, 8), (1300, 8), (1400, 4.5), (1600, 12)):
        reference = (
            Scene(doc)
            .add(replace(leaf, clip=RectangleClip(0, 0, front, 12, inverse=inverse)))
            .compile()
        )
        assert (
            rasterize(result.document.dumps(), time, (32, 32)).rgba
            == rasterize(reference.document.dumps(), time, (32, 32)).rgba
        )


@pytest.mark.parametrize(
    "keys",
    (
        (),
        ((1, (0, 0, 1, 1)), (0, (0, 0, 1, 1))),
        ((0, (1, 0, 0, 1)),),
        ((0, (0, 1, 1, 0)),),
        ((float("nan"), (0, 0, 1, 1)),),
        ((0, (0, 0, float("inf"), 1)),),
        ((0, (0, 0, 1, 1)),) * 3,
    ),
)
def test_invalid_known_curves_are_rejected(keys):
    with pytest.raises(ValueError):
        RectangleKeyframes(keys)


@pytest.mark.parametrize("inverse", (False, True))
def test_native_curve_preserves_cropped_clock_pauses_resets_and_event_cost(inverse):
    from kara_templater import SceneCompileError

    doc = Document.create(width=32, height=32)
    leaf = PathObject(
        id="native",
        lifetime=Lifetime(1.1, 1.8),
        clock_start=1,
        path=VectorPath.rectangle(16, 12),
        clip=RectangleClip(0, 0, 16, 12, inverse=inverse, deform=curve()),
    )
    scene = Scene(doc).add(leaf)
    result = scene.compile(native_tweens=True, budget=SceneBudget(fps=1, max_events=4))
    assert result.event_count == 4
    assert result.objects[0].strategy == "native-clip"
    assert result.objects[0].sample_interval is None
    events = result.document.lines
    assert r"\t(-100,100,1," in events[0].text
    assert r"\t(" not in events[1].text  # plateau
    assert r"\t(" not in events[-1].text  # held tail
    with pytest.raises(SceneCompileError, match="event budget"):
        scene.compile(native_tweens=True, budget=SceneBudget(max_events=3))
    for time, front in (
        (1100, 4),
        (1150, 6),
        (1200, 8),
        (1390, 8),
        (1400, 2),
        (1440, 4),
        (1500, 7),
        (1600, 12),
    ):
        reference = (
            Scene(doc)
            .add(replace(leaf, clip=RectangleClip(0, 0, front, 12, inverse=inverse)))
            .compile()
        )
        assert (
            rasterize(result.document.dumps(), time, (32, 32)).rgba
            == rasterize(reference.document.dumps(), time, (32, 32)).rgba
        )


def test_native_curve_maps_local_bounds_and_falls_back_for_custom_animation():
    from kara_templater import StateFunction, Vec2, VisualState

    doc = Document.create(width=64, height=32)
    leaf = PathObject(
        id="local",
        lifetime=Lifetime(0, 1),
        path=VectorPath.rectangle(16, 12),
        state=VisualState(position=Vec2(8, 6), scale=Vec2(2, 1)),
        clip=RectangleClip(0, 0, 16, 12, space="local", deform=curve()),
    )
    result = Scene(doc).add(leaf).compile(native_tweens=True)
    assert result.objects[0].strategy == "native-clip"
    assert r"\clip(8,6,8,18)" in result.document.lines[0].text
    assert r"\clip(8,6,24,18)" in result.document.lines[0].text
    animated = leaf.animate(
        StateFunction(lambda state, t: replace(state, scale=state.scale * (1 + t * t))),
        duration=1,
    )
    fallback = Scene(doc).add(animated).compile(native_tweens=True)
    assert fallback.objects[0].strategy == "sampled"
    group = ObjectGroup(
        id="coverage", lifetime=leaf.lifetime, children=(leaf,), coverage=Coverage()
    )
    assert (
        Scene(doc).add(group).compile(native_tweens=True).objects[0].strategy
        == "coverage"
    )


@pytest.mark.parametrize("inverse", (False, True))
def test_native_empty_mask_matches_normal_and_inverse_visibility(inverse):
    doc = Document.create(width=32, height=32)
    leaf = PathObject(
        id="empty",
        lifetime=Lifetime(0, 1),
        path=VectorPath.rectangle(16, 12),
        clip=RectangleClip(
            0,
            0,
            16,
            12,
            inverse=inverse,
            deform=RectangleKeyframes(
                (
                    (0, (0, 0, 0, 12)),
                    (0.2, (0, 0, 0, 12)),
                    (0.4, (0, 0, 8, 12)),
                )
            ),
        ),
    )
    actual = Scene(doc).add(leaf).compile(native_tweens=True)
    reference = Scene(doc)
    if inverse:
        reference.add(replace(leaf, clip=None))
    expected = reference.compile()
    for time in (0, 100, 200):
        assert (
            rasterize(actual.document.dumps(), time, (32, 32)).rgba
            == rasterize(expected.document.dumps(), time, (32, 32)).rgba
        )


def test_overridden_curve_evaluation_is_not_assumed_linear():
    class CurvedRectangle(RectangleKeyframes):
        def bounds_at(
            self, time: float, *, before: bool = False
        ) -> tuple[float, float, float, float]:
            left, top, right, bottom = super().bounds_at(time, before=before)
            return left, top, right * right / 8, bottom

    leaf = PathObject(
        id="custom",
        lifetime=Lifetime(0, 1),
        path=VectorPath.rectangle(16, 12),
        clip=RectangleClip(
            0,
            0,
            16,
            12,
            deform=CurvedRectangle(
                (
                    (0, (0, 0, 0, 12)),
                    (1, (0, 0, 8, 12)),
                )
            ),
        ),
    )
    result = (
        Scene(Document.create(width=32, height=32))
        .add(leaf)
        .compile(native_tweens=True)
    )
    assert result.objects[0].strategy == "sampled"
