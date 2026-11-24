"""Continuous RGB gradients and shader paint for Hook drawings."""

from dataclasses import dataclass
from typing import Literal

from .composition import Color
from .geometry import Vec2, finite


def _mix(a: Color, b: Color, progress: float) -> Color:
    p = max(0.0, min(1.0, progress))
    return Color(
        round(a.red + (b.red - a.red) * p),
        round(a.green + (b.green - a.green) * p),
        round(a.blue + (b.blue - a.blue) * p),
    )


@dataclass(frozen=True)
class Extrusion:
    """A solid side swept from a drawing's hard silhouette in local script pixels.

    Offset is the vector from front to back. The side follows the face's
    transforms and opacity, and keeps its own color during a lyric wipe.
    back_color shades the side from color at the face to back_color at full depth.
    Zero offset gives a flat drawing. Hook output supports this appearance.
    """

    offset: Vec2
    color: Color
    back_color: Color | None = None


@dataclass(frozen=True)
class ShaderPaint:
    """GLSL applied per covered pixel after the normal material and feather.

    The body can modify RGB ink and opacity alpha. local and screen are script
    pixel coordinates, time is signed seconds from the object clock, coverage
    is the native mask, and component is 0 for fill, 1 for outline, 2 for
    shadow. Numeric parameters are accessible through item(data + offset).
    Optional functions can contain Metashade-generated GLSL definitions.
    """

    source: str
    parameters: tuple[float, ...] = ()
    functions: str = ""

    def __post_init__(self) -> None:
        if not self.source.strip() or "//!" in self.source + self.functions:
            raise ValueError("shader paint requires a GLSL function body")
        finite(*self.parameters)


@dataclass(frozen=True)
class ColorStop:
    """An RGB color at a finite script-space position along a paint field axis.

    ColorRamp requires ordered stops.
    """

    position: float
    color: Color

    def __post_init__(self) -> None:
        finite(self.position)


@dataclass(frozen=True)
class ColorRamp:
    """Piecewise linear colors at absolute script coordinates; ends clamp."""

    stops: tuple[ColorStop, ...]

    def __post_init__(self) -> None:
        if len(self.stops) < 2 or any(
            a.position >= b.position
            for a, b in zip(self.stops, self.stops[1:], strict=False)
        ):
            raise ValueError("a color ramp needs at least two strictly ordered stops")

    def at(self, position: float) -> Color:
        """Evaluate the RGB ramp at a script-space position, extending endpoint colors outside its stops."""
        finite(position)
        for a, b in zip(self.stops, self.stops[1:], strict=False):
            if position <= b.position:
                return _mix(
                    a.color,
                    b.color,
                    (position - a.position) / (b.position - a.position),
                )
        return self.stops[-1].color


@dataclass(frozen=True, kw_only=True)
class LinearGradient:
    """An x/y gradient for fill, outline, or both; screen coordinates by default.

    The hook shades independent fill and outline ramps continuously. Local
    space attaches color stops to the untransformed drawing.
    """

    fill: ColorRamp | None = None
    outline: ColorRamp | None = None
    axis: Literal["x", "y"] = "x"
    space: Literal["screen", "local"] = "screen"

    def __post_init__(self) -> None:
        if self.axis not in ("x", "y"):
            raise ValueError("gradient axis must be x or y")
        if self.space not in ("screen", "local"):
            raise ValueError("gradient space must be screen or local")
        if self.fill is None and self.outline is None:
            raise ValueError("gradient requires a fill or outline ramp")

    @property
    def bounds(self) -> tuple[float, float]:
        """The script-space interval covered by the configured color ramps."""
        ramps = [r for r in (self.fill, self.outline) if r is not None]
        return min(r.stops[0].position for r in ramps), max(
            r.stops[-1].position for r in ramps
        )
