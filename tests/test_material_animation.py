"""Common color interpolation handles overshoot without invalid RGB output."""

import pytest

from kara_templater import BLUE, RED, StatePatch, Tween, VisualState


@pytest.mark.parametrize("rate,expected", ((2, BLUE), (-1, RED)))
def test_color_tween_clamps_overshooting_channels(rate, expected):
    state = Tween(StatePatch(fill=BLUE), rate=lambda p: rate).sample(
        VisualState(fill=RED), 0.5
    )
    assert state.fill == expected


@pytest.mark.parametrize("rate", (float("nan"), float("inf")))
def test_color_tween_rejects_nonfinite_easing(rate):
    with pytest.raises(ValueError):
        Tween(StatePatch(fill=BLUE), rate=lambda p: rate).sample(VisualState(fill=RED), 0.5)
