"""Continuous RGB gradients, extrusion, and shader paint for scene rendering."""

from dataclasses import dataclass
from typing import ClassVar, Literal

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
    Zero offset gives a flat drawing. Browser preview and playback shaders support this appearance.
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


type PaintValue = float | Color | Vec2


@dataclass(frozen=True)
class _PaintTrack:
    """Piecewise-linear material argument on its object's local clock."""

    keys: tuple[tuple[float, float], ...]


@dataclass(frozen=True)
class PaintControl:
    """Describe a browser control for a named paint input.

    Bounds are inclusive and apply to a scalar or to both vector axes.
    Step is the suggested increment for a preview control. Labels, units,
    and group names are display text. Order sorts controls within a group.
    """

    bounds: tuple[float, float] | None = None
    step: float | None = None
    unit: str = ""
    label: str = ""
    group: str = ""
    order: int = 0

    def __post_init__(self) -> None:
        if self.bounds is not None:
            finite(*self.bounds)
            if self.bounds[0] >= self.bounds[1] or max(map(abs, self.bounds)) > 3.4028234663852886e38:
                raise ValueError("paint control bounds must be increasing and fit in f32")
        if self.step is not None:
            finite(self.step)
            if self.step <= 0:
                raise ValueError("paint control step must be positive")


@dataclass(frozen=True)
class PaintInput:
    """A named material value that a preview host may update while playing.

    Uses of the same name share one value and must have matching defaults
    and control declarations. An omitted control keeps the host's existing
    presentation for unbounded inputs.
    """

    name: str
    value: PaintValue
    control: PaintControl | None = None

    def __post_init__(self) -> None:
        if not self.name or not self.name.isascii() or not self.name.isidentifier():
            raise ValueError("paint input requires an ASCII identifier")
        if self.control is None:
            return
        if isinstance(self.value, Color):
            if self.control.bounds is not None or self.control.step is not None:
                raise ValueError("color inputs do not support numeric bounds or steps")
            return
        values = (self.value.x, self.value.y) if isinstance(self.value, Vec2) else (self.value,)
        if any(isinstance(value, bool) for value in values):
            raise TypeError("paint inputs require numeric values, colors or vectors")
        finite(*values)
        if self.control.bounds is not None:
            lower, upper = self.control.bounds
            if not all(lower <= value <= upper for value in values):
                raise ValueError("paint input default falls outside the control bounds")


class MaterialEffect:
    """A reusable WGSL function evaluated after sampling a coverage plane.

    Define ``shade(material: vec4<f32>, ctx: KaraPaintContext, ...)`` to
    return straight RGB and opacity. The renderer provides ``ctx.local`` and
    ``ctx.screen`` in script pixels, ``ctx.coverage`` in 0..1, ``ctx.time`` in
    seconds from the effect start, and ``ctx.progress`` in 0..1. Component
    indices are 0 for fill, 1 for outline, 2 for shadow and 3 for extrusion.
    Additional arguments follow ``parameters()`` in order. Float, Color and
    Vec2 become f32, vec3<f32> in 0..1, and vec2<f32> respectively.
    """

    wgsl: ClassVar[str] = ""
    entry_point: ClassVar[str] = "shade"

    def parameters(self) -> tuple[PaintValue | PaintInput, ...]:
        """Return the values supplied as arguments after material and context."""
        return ()

    def _arguments(self) -> tuple[PaintValue | PaintInput | _PaintTrack, ...]:
        return self.parameters()


@dataclass(frozen=True, kw_only=True)
class MaterialClip:
    """Apply a WGSL effect to one or all coverage planes over a local interval.

    Start is relative to the object's clock, and an omitted duration extends
    to the end of its lifetime. Effects on a plane run in declaration order.
    """

    effect: MaterialEffect
    start: float = 0.0
    duration: float | None = None
    target: Literal["fill", "outline", "shadow", "all"] = "fill"

    def __post_init__(self) -> None:
        finite(self.start)
        if self.target not in ("fill", "outline", "shadow", "all"):
            raise ValueError("material clip target must be fill, outline, shadow or all")
        if self.duration is not None:
            finite(self.duration)
            if self.duration <= 0:
                raise ValueError("material clip duration must be positive")


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

    The scene shader shades independent fill and outline ramps continuously. Local
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
