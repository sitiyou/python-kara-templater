
import pytest

from kara_templater import (
    BLACK,
    RED,
    WHITE,
    Color,
    ColorRamp,
    ColorStop,
    Lifetime,
    LinearGradient,
    TextObject,
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


