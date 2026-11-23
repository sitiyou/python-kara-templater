
import pytest

from kara_templater import (
    BLACK,
    BLUE,
    RED,
    WHITE,
    Color,
    ColorRamp,
    ColorStop,
    Lifetime,
    LinearGradient,
    SoftSweep,
    TextObject,
    VisualState,
)
from kara_templater.scene import ObjectGroup


def ramp(a=BLACK, b=WHITE):
    return ColorRamp((ColorStop(0, a), ColorStop(64, b)))


def test_ramp_clamps_and_interpolates_encoded_rgb():
    value = ColorRamp((ColorStop(0, BLACK), ColorStop(10, RED), ColorStop(20, WHITE)))
    assert value.at(-1) == BLACK
    assert value.at(5) == Color(128, 0, 0)
    assert value.at(15) == Color(255, 128, 128)
    assert value.at(30) == WHITE
    with pytest.raises(ValueError):
        ColorRamp((ColorStop(0, BLACK), ColorStop(0, WHITE)))


def test_sweep_channels_have_independent_widths_and_seek_is_pure():
    field = SoftSweep(
        left=0,
        right=64,
        start=0.5,
        duration=1,
        fill=(BLACK, WHITE),
        outline=(RED, BLUE),
        width=8,
        outline_width=16,
    )

    def at(time):
        bands = field.bands(0, 64, time, VisualState())
        assert len(bands) <= field.max_bands
        assert [x for b in bands for x in range(b.start, b.end)] == list(range(64))
        return {x: (b.fill, b.outline) for b in bands for x in range(b.start, b.end)}

    middle = at(1)
    assert middle[27][0] == WHITE
    assert middle[27][1] != BLUE
    assert at(0)[32] == (BLACK, RED)
    assert at(2)[32] == (WHITE, BLUE)
    assert at(1) == middle


def test_material_constraints_and_preflight():
    field = LinearGradient(fill=ramp())
    with pytest.raises(ValueError, match="group paint"):
        ObjectGroup(id="group", children=(), lifetime=Lifetime(0, 2), material=field)


def test_material_survives_geometry_conversion_and_copy():
    from kara_templater import text_to_path

    field = LinearGradient(fill=ramp())
    text = TextObject(id="text", text="W", lifetime=Lifetime(0, 2), material=field)
    assert text_to_path(text).material is field
    assert text.copy(id="copy", delay=1).material is field


def test_soft_sweep_exposes_eased_transition_center_including_padding():
    field = SoftSweep(
        left=100,
        right=200,
        start=1,
        duration=2,
        fill=(WHITE, RED),
        width=20,
        outline=(WHITE, BLUE),
        outline_width=40,
        rate=lambda p: p * p,
    )
    assert [field.front_at(t) for t in (0, 1, 2, 3, 4)] == [80, 80, 115, 220, 220]
    # The half-mixed band is centered on the same position, for either width.
    bands = field.bands(114, 116, 2, VisualState())
    assert len(bands) == 2
    assert bands[0].fill.green < bands[1].fill.green  # unsung lies to the right


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_soft_sweep_front_rejects_nonfinite_time(value: float):
    field = SoftSweep(left=0, right=100, start=0, duration=1, fill=(WHITE, RED))
    with pytest.raises(ValueError):
        field.front_at(value)
