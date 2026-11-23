"""Optional activity declarations optimize common sampling without guessing callbacks."""

from dataclasses import dataclass

import pytest

from kara_templater import (
    PINK,
    WHITE,
    Lifetime,
    SoftSweep,
    TextObject,
    VisualState,
)
from kara_templater.paint_fields import PaintBand
from kara_templater.scene_animation import TimeSpan


@dataclass(frozen=True)
class Unbounded:
    field: SoftSweep

    @property
    def axis(self):
        return self.field.axis

    @property
    def max_bands(self):
        return self.field.max_bands

    @property
    def breakpoints(self):
        return self.field.breakpoints

    def bands(
        self, start: int, end: int, time: float, base: VisualState
    ) -> tuple[PaintBand, ...]:
        return self.field.bands(start, end, time, base)


def test_invalid_activity_and_missing_endpoints_are_rejected():
    @dataclass(frozen=True)
    class Declared(Unbounded):
        active_intervals: tuple[TimeSpan, ...] = ()

    field = SoftSweep(left=0, right=100, start=1, duration=1, fill=(WHITE, PINK))
    for intervals in (
        (TimeSpan(1, 1),),
        (TimeSpan(-1, 2),),
        (TimeSpan(1, 4),),
        (TimeSpan(0.5, 2),),
    ):
        with pytest.raises(ValueError, match="paint activity"):
            TextObject(
                id="invalid",
                text="x",
                lifetime=Lifetime(0, 3),
                material=Declared(field, intervals),
            )
