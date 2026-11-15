from typing import assert_type

from kara_templater import (
    BLUE,
    RED,
    ColorRamp,
    ColorStop,
    LinearGradient,
    PaintBand,
    PaintField,
    SoftSweep,
    VisualState,
)


def evaluate(field: PaintField) -> tuple[PaintBand, ...]:
    return field.bands(0, 1280, 1, VisualState())


gradient = LinearGradient(fill=ColorRamp((ColorStop(0, RED), ColorStop(100, BLUE))))
sweep = SoftSweep(left=0, right=100, start=0, duration=1, fill=(RED, BLUE))
assert_type(evaluate(gradient), tuple[PaintBand, ...])
assert_type(evaluate(sweep), tuple[PaintBand, ...])
assert_type(sweep.front_at(0.5), float)
