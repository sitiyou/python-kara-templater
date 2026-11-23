"""RGB paint fields for scene evaluation and GPU gradient rendering.
"""

from collections.abc import Callable
from dataclasses import dataclass
from math import ceil, floor
from typing import Literal, Protocol, runtime_checkable

from .composition import Color
from .geometry import Vec2, finite
from .scene_animation import TimeSpan, VisualState, linear_rate


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
class PaintBand:
    """A half-open integer interval with resolved fill and outline colors.

    Paint fields return these bounded bands for standard ASS compilation.
    """

    start: int
    end: int
    fill: Color
    outline: Color


@runtime_checkable
class PaintField(Protocol):
    """Pure local-time field. Bands must exactly partition the requested domain.

    Breakpoints delimit temporal discontinuities and changes of motion. An empty
    tuple declares a static field. max_bands bounds every invocation.
    Times are signed seconds from the owning object's clock origin; absolute
    breakpoints cannot precede Scene zero or exceed the object's display end.
    """

    @property
    def axis(self) -> Literal["x", "y"]:
        """The x or y script-space axis along which bands are encoded."""
        ...

    @property
    def max_bands(self) -> int:
        """The maximum band count promised by this paint field for preflight."""
        ...

    @property
    def breakpoints(self) -> tuple[float, ...]:
        """Declared seconds boundaries required for deterministic material sampling."""
        ...

    def bands(
        self, start: int, end: int, time: float, base: VisualState
    ) -> tuple[PaintBand, ...]:
        """Evaluate bounded colored bands for the supplied visual state and seconds time."""
        ...


@runtime_checkable
class PaintActivity(Protocol):
    """Optional promise that a paint field is time-constant outside these spans.

    Intervals use signed local seconds, and their endpoints must also be breakpoints.
    Changes to the incoming VisualState are sampled independently. Omit this
    protocol when an arbitrary callback cannot make the constancy guarantee;
    the compiler then samples its complete visible lifetime.
    """

    @property
    def active_intervals(self) -> tuple[TimeSpan, ...]:
        """Finite positive-duration local intervals where time changes the field."""
        ...


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


def _settings(axis: str, step: int) -> None:
    if axis not in ("x", "y") or type(step) is not int or step < 1:
        raise ValueError("paint fields require x/y axis and positive integer step")


def _bands(
    start: int,
    end: int,
    left: float,
    right: float,
    step: int,
    colors: Callable[[float], tuple[Color, Color]],
) -> tuple[PaintBand, ...]:
    first, last = max(start, floor(left)), min(end, ceil(right))
    cuts = sorted(
        {start, end, *range(first, last + 1, step), max(start, min(end, last))}
    )
    result: list[PaintBand] = []
    for a, b in zip(cuts, cuts[1:], strict=False):
        fill, outline = colors((a + b) / 2)
        if result and result[-1].fill == fill and result[-1].outline == outline:
            previous = result.pop()
            a = previous.start
        result.append(PaintBand(a, b, fill, outline))
    return tuple(result)


@dataclass(frozen=True, kw_only=True)
class LinearGradient:
    """An x/y gradient for fill, outline, or both; screen coordinates by default.

    The hook shades independent fill and outline ramps continuously. Local
    space attaches color stops to the untransformed drawing. ASS compilation
    rejects paint fields. The bands() method samples the field at integer steps.
    """

    fill: ColorRamp | None = None
    outline: ColorRamp | None = None
    axis: Literal["x", "y"] = "x"
    step: int = 1
    space: Literal["screen", "local"] = "screen"

    def __post_init__(self) -> None:
        _settings(self.axis, self.step)
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

    @property
    def max_bands(self) -> int:
        """Declared upper bound on emitted color bands at the configured step."""
        left, right = self.bounds
        return ceil((right - left) / self.step) + 4

    @property
    def breakpoints(self) -> tuple[float, ...]:
        """Time boundaries required by this field; a static gradient has none."""
        return ()

    def bands(
        self, start: int, end: int, time: float, base: VisualState
    ) -> tuple[PaintBand, ...]:
        """Resolve fill/outline colors into bounded integer bands for the evaluated drawing state."""
        left, right = self.bounds
        return _bands(
            start,
            end,
            left,
            right,
            self.step,
            lambda p: (
                base.fill if self.fill is None else self.fill.at(p),
                base.outline if self.outline is None else self.outline.at(p),
            ),
        )


@dataclass(frozen=True, kw_only=True)
class SoftSweep:
    """Left-to-right (or top-to-bottom) sweep; pairs are (unsung, sung).

    Widths are script pixels. The front travels past both ends so the declared
    span is completely unsung at start and completely sung at start+duration.
    start and duration are local seconds from the owning object's clock origin.
    """

    left: float
    right: float
    start: float
    duration: float
    fill: tuple[Color, Color] | None = None
    outline: tuple[Color, Color] | None = None
    width: float = 24
    outline_width: float | None = None
    axis: Literal["x", "y"] = "x"
    step: int = 1
    rate: Callable[[float], float] = linear_rate

    def __post_init__(self) -> None:
        _settings(self.axis, self.step)
        finite(
            self.left,
            self.right,
            self.start,
            self.duration,
            self.width,
            self.effective_outline_width,
        )
        if self.right <= self.left or self.start < 0 or self.duration <= 0:
            raise ValueError(
                "sweep requires positive span/duration and nonnegative start"
            )
        if min(self.width, self.effective_outline_width) < 0:
            raise ValueError("sweep widths cannot be negative")
        if self.fill is None and self.outline is None:
            raise ValueError("sweep requires fill or outline colors")

    @property
    def active_intervals(self) -> tuple[TimeSpan, ...]:
        """Only the sweep interval changes with time; both endpoints clamp."""
        return (TimeSpan(self.start, self.start + self.duration),)

    @property
    def effective_outline_width(self) -> float:
        """The explicit outline front width or the fill width when none was supplied."""
        return self.width if self.outline_width is None else self.outline_width

    @property
    def max_width(self) -> float:
        """The larger fill/outline transition width used to cover both sweep endpoints."""
        return max(
            self.width if self.fill else 0,
            self.effective_outline_width if self.outline else 0,
        )

    @property
    def max_bands(self) -> int:
        """Declared worst-case color-band count at the selected spatial step."""
        return ceil(self.max_width / self.step) + 4

    @property
    def breakpoints(self) -> tuple[float, ...]:
        """The local start and end seconds required by material sampling."""
        return (self.start, self.start + self.duration)

    def front_at(self, time: float) -> float:
        """Transition center in script pixels at field-local seconds.

        It travels half the largest transition width beyond each endpoint and
        clamps outside the singing interval, matching the color field's timing.
        """
        finite(time)
        if time <= self.start:
            progress = 0.0
        elif time >= self.start + self.duration:
            progress = 1.0
        else:
            progress = self.rate((time - self.start) / self.duration)
            finite(progress)
        return (
            self.left
            - self.max_width / 2
            + (self.right - self.left + self.max_width) * max(0, min(1, progress))
        )

    def bands(
        self, start: int, end: int, time: float, base: VisualState
    ) -> tuple[PaintBand, ...]:
        """Evaluate the independent fill/outline fronts into integer color bands at seconds time."""
        finite(time)
        if time <= self.start or time >= self.start + self.duration:
            index = int(time >= self.start + self.duration)
            return (
                PaintBand(
                    start,
                    end,
                    base.fill if self.fill is None else self.fill[index],
                    base.outline if self.outline is None else self.outline[index],
                ),
            )
        front = self.front_at(time)

        def color(
            pair: tuple[Color, Color] | None,
            fallback: Color,
            width: float,
            position: float,
        ) -> Color:
            if pair is None:
                return fallback
            amount = (
                float(position < front)
                if width == 0
                else (front - position) / width + 0.5
            )
            return _mix(*pair, amount)

        return _bands(
            start,
            end,
            front - self.max_width / 2,
            front + self.max_width / 2,
            self.step,
            lambda p: (
                color(self.fill, base.fill, self.width, p),
                color(self.outline, base.outline, self.effective_outline_width, p),
            ),
        )
