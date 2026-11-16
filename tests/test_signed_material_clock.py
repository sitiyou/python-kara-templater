"""Material clocks retain meaning when visibility precedes the local origin."""

from dataclasses import dataclass, replace
from typing import Literal

import pytest

from kara_templater import (
    RED,
    Coverage,
    Document,
    Glow,
    GlowFunction,
    Lifetime,
    ObjectGroup,
    PathObject,
    RectangleClip,
    RectangleFunction,
    Scene,
    SceneBudget,
    ScopeOpacity,
    StatePatch,
    TimeSpan,
    Vec2,
    VectorPath,
    VisualState,
)
from kara_templater._raster import rasterize
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


@pytest.mark.parametrize("coverage", (False, True))
def test_signed_material_glow_and_opacity_match_shifted_origin_reference(coverage):
    def build(origin):
        offset = origin - 0.5
        paint = ShiftedPaint(offset)
        leaf = PathObject(
            id="shape",
            lifetime=Lifetime(0.5, 2),
            clock_start=origin,
            path=VectorPath.rectangle(12, 12),
            state=VisualState(position=Vec2(15, 15)),
            material=paint,
            clip=RectangleClip(
                0,
                0,
                48,
                48,
                deform=RectangleFunction(
                    lambda time: (0, 0, 20 + 10 * max(0, min(1, time + offset)), 48),
                    breakpoints=paint.breakpoints,
                ),
            ),
        )
        return ObjectGroup(
            id="root",
            lifetime=leaf.lifetime,
            clock_start=origin,
            children=(leaf,),
            coverage=Coverage(
                glows={
                    leaf.id: GlowFunction(
                        lambda state, time: Glow(
                            RED, blur=2 * max(0, min(1, time + offset))
                        ),
                        max_blur=2,
                        max_border=0,
                        breakpoints=paint.breakpoints,
                        required_interval=TimeSpan(-offset, 1 - offset),
                    )
                },
                scope_opacities={
                    leaf.id: (
                        ScopeOpacity(
                            "root",
                            lambda time: 0.5 + 0.5 * max(0, min(1, time + offset)),
                            breakpoints=paint.breakpoints,
                        ),
                    )
                },
            )
            if coverage
            else None,
        )

    doc = Document.create(width=48, height=48)
    outputs = tuple(
        Scene(doc)
        .add(build(origin))
        .compile(budget=SceneBudget(fps=20))
        .document.dumps()
        for origin in (1, 0.5)
    )
    for time in (550, 850, 1250, 1750):
        actual = rasterize(outputs[0], time, (48, 48)).rgba
        assert any(actual[3::4])
        assert actual == rasterize(outputs[1], time, (48, 48)).rgba


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
    with pytest.raises(ValueError, match="glow|opacity scope"):
        Scene(Document.create()).add(group).compile()
    assert calls == []
