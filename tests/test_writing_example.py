"""Timeline boundary validation for writing animations."""


import pytest

from kara_templater import (
    StateFunction,
    Timeline,
)


@pytest.mark.parametrize("point", [-0.1, 1.1, float("nan"), float("inf")])
def test_invalid_timeline_boundary_does_not_modify_schedule(point: float):
    animation = StateFunction(lambda state, progress: state)
    timeline = Timeline().wait(0.2)
    with pytest.raises(ValueError):
        timeline.play(animation, duration=1, breakpoints=(point,))
    assert timeline.clips == ()
    timeline.play(animation, duration=1)
    assert timeline.clips[0].start == 0.2
