"""Material clocks retain meaning when visibility precedes the local origin."""

from dataclasses import dataclass, replace
from typing import Literal

import pytest

from kara_templater import (
    RED,
    Coverage,
    Document,
    GlowFunction,
    Lifetime,
    ObjectGroup,
    PathObject,
    RectangleClip,
    RectangleFunction,
    Scene,
    ScopeOpacity,
    StatePatch,
    TimeSpan,
    VectorPath,
    VisualState,
)
from kara_templater.paint_fields import PaintBand


@dataclass(frozen=True)
class ShiftedPaint:
    offset: float
    axis: Literal["x"] = "x"
    max_bands: int = 1

    @property
    def breakpoints(self) -> tuple[float, float]:
        return (-self.offset, 1 - self.offset)

    @property
    def active_intervals(self) -> tuple[TimeSpan, ...]:
        return (TimeSpan(*self.breakpoints),)

    def bands(
        self, start: int, end: int, time: float, base: VisualState
    ) -> tuple[PaintBand, ...]:
        state = StatePatch(fill=RED).interpolate(
            base, max(0, min(1, time + self.offset))
        )
        return (PaintBand(start, end, state.fill, state.outline),)


@pytest.mark.parametrize("kind", ("glow", "interval", "scope", "paint", "mask"))
def test_material_times_before_scene_zero_fail_before_sampling(kind):
    calls = []
    leaf = PathObject(
        id="shape",
        lifetime=Lifetime(0.5, 2),
        clock_start=1,
        path=VectorPath.rectangle(5, 5),
    )
    if kind == "mask":
        with pytest.raises(ValueError, match="clip breakpoint"):
            replace(
                leaf,
                clip=RectangleClip(
                    0,
                    0,
                    10,
                    10,
                    deform=RectangleFunction(
                        lambda time: (0, 0, 10, 10),
                        breakpoints=(-1.1,),
                    ),
                ),
            )
        return
    if kind == "paint":
        with pytest.raises(ValueError, match="paint breakpoint"):
            replace(leaf, material=ShiftedPaint(1.1))
        return

    def opacity(time: float) -> float:
        calls.append(time)
        return 1

    glow = GlowFunction(
        lambda state, time: calls.append(time),
        max_blur=0,
        max_border=0,
        breakpoints=(-1.1,) if kind == "glow" else (),
        required_interval=TimeSpan(-1.1, 0) if kind == "interval" else None,
    )
    group = ObjectGroup(
        id="root",
        lifetime=leaf.lifetime,
        clock_start=1,
        children=(leaf,),
        coverage=Coverage(
            glows={leaf.id: glow},
            scope_opacities={
                leaf.id: (
                    ScopeOpacity(
                        "root",
                        opacity,
                        breakpoints=(-1.1,),
                    ),
                )
            }
            if kind == "scope"
            else {},
        ),
    )
    with pytest.raises(ValueError, match="coverage groups"):
        Scene(Document.create()).add(group).ass.compile()
    assert calls == []
