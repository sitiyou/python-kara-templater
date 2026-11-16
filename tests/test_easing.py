"""Reusable easing controls common animation without a second clock model."""

import pytest

from kara_templater import (
    BackRate,
    StatePatch,
    Tween,
    Vec2,
    VisualState,
    ease_in,
    ease_out,
    there_and_back,
)


def test_asymmetric_rise_hold_fall_drives_common_tween_and_seek():
    rate = there_and_back(peak_at=0.25, return_at=0.5, rise=ease_in, fall=ease_out)
    tween = Tween(StatePatch(position=Vec2(8, 0)), rate=rate)
    for progress, x in ((0.75, 2), (0.125, 2), (0.4, 8), (1, 0), (0, 0), (0.75, 2)):
        assert tween.sample(VisualState(), progress).position == Vec2(x, 0)
    assert there_and_back(0.5) == 1


@pytest.mark.parametrize(
    "peak,end", ((0, 0.5), (0.7, 0.5), (0.5, 1), (float("nan"), 0.5))
)
def test_easing_factory_and_direct_value_reject_invalid_knots(peak, end):
    with pytest.raises(ValueError):
        there_and_back(peak_at=peak, return_at=end)
    with pytest.raises(ValueError):
        BackRate(peak, end, ease_in, ease_out)
