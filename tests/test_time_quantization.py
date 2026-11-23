"""Output diagnostics distinguish sampled collapse from native interpolation."""


import pytest

from kara_templater import (
    AnimationClip,
    Document,
    Lifetime,
    PathObject,
    Scene,
    StatePatch,
    Tween,
    VectorPath,
)


def test_native_millisecond_tween_does_not_report_sampled_collapse():
    child = PathObject(
        id="fade",
        lifetime=Lifetime(0, 2),
        path=VectorPath.rectangle(8, 8),
        animations=(AnimationClip(1, 0.004, Tween(StatePatch(opacity=0.5))),),
    )
    scene = Scene(Document.create(width=32, height=32)).add(child)
    result = scene.ass.compile(native_tweens=True)
    assert result.objects[0].strategy == "native-tween"
    assert not result.diagnostics
    assert r"\t(1000,1004," in result.document.lines[-1].text


@pytest.mark.parametrize(
    "start,end,expected",
    (
        (0.004, 0.024, (0, 20)),
        (0.005, 0.025, (0, 20)),
        (0.015, 0.035, (20, 40)),
    ),
)
def test_scene_event_boundaries_round_half_steps_to_even_centiseconds(
    start, end, expected
):
    node = PathObject(
        id="static", lifetime=Lifetime(start, end), path=VectorPath.rectangle(8, 8)
    )
    result = Scene(Document.create(width=32, height=32)).add(node).ass.compile()
    event = result.document.lines[-1]
    assert (event.start_time, event.end_time) == expected
    assert result.max_time_quantization == pytest.approx(
        max(abs(start - expected[0] / 1000), abs(end - expected[1] / 1000))
    )
