"""Actual E08 ASS must preserve explicit pen-up intervals off the 20ms grid."""

from dataclasses import replace

import pytest

from examples.scene_writing import build
from kara_templater import (
    PINK,
    Document,
    Lifetime,
    PathObject,
    Scene,
    SceneTimeline,
    StateFunction,
    VectorPath,
    VisualState,
)
from tools.validate_writing import pen


def test_writing_pen_starts_and_stops_at_declared_boundaries():
    script = build().compile().document.dumps()
    for start, end in ((300, 1200), (1350, 2250), (2400, 2900), (3050, 4500)):
        assert pen(script, start - 1) is None, start
        assert pen(script, start) is not None, start
        assert pen(script, start + 1) is not None, start
        assert pen(script, end - 1) is not None, end
        assert pen(script, end) is None, end
        assert pen(script, end + 1) is None, end


def test_repeated_timeline_preserves_off_grid_visibility_boundaries():
    def visibility(state: VisualState, progress: float) -> VisualState:
        return replace(state, opacity=float(0.35 <= progress < 0.75))

    timeline = (
        SceneTimeline()
        .wait(0.1)
        .play(
            StateFunction(visibility, frozenset(("opacity",))),
            duration=1,
            hold=False,
            breakpoints=(0.35, 0.75),
        )
        .repeat(2)
    )
    node = PathObject(
        id="pulse",
        path=VectorPath.circle(7),
        lifetime=Lifetime(1, 3.3),
        state=VisualState(fill=PINK, opacity=0),
        animations=timeline.clips,
    )
    script = Scene(Document.create()).add(node).compile().document.dumps()
    # Object birth, initial wait and repeated schedule all shift the boundaries.
    for start, end in ((1450, 1850), (2550, 2950)):
        for time in (start - 1, end, end + 1):
            assert pen(script, time) is None, time
        for time in (start, start + 1, end - 1):
            assert pen(script, time) is not None, time


@pytest.mark.parametrize("point", [-0.1, 1.1, float("nan"), float("inf")])
def test_invalid_timeline_boundary_does_not_modify_schedule(point: float):
    animation = StateFunction(lambda state, progress: state)
    timeline = SceneTimeline().wait(0.2)
    with pytest.raises(ValueError):
        timeline.play(animation, duration=1, breakpoints=(point,))
    assert timeline.clips == ()
    timeline.play(animation, duration=1)
    assert timeline.clips[0].start == 0.2
