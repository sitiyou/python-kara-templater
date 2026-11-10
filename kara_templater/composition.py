"""Resolve body coverage and appearance without assuming an ASS layer strategy.

These are semantic regions, not instructions to clip blurred glyphs at every
region edge. The output backend must validate whether it can realize them.
"""

from dataclasses import dataclass
from itertools import pairwise
from string import hexdigits

from .timeline import HighlightTrack, Region, _finite


@dataclass(frozen=True)
class Color:
    red: int
    green: int
    blue: int

    def __post_init__(self):
        for channel in (self.red, self.green, self.blue):
            if type(channel) is not int or not 0 <= channel <= 255:
                raise ValueError("RGB channels must be integers in 0..255")

    @classmethod
    def hex(cls, value: str):
        if (
            not isinstance(value, str)
            or len(value) != 7
            or not value.startswith("#")
            or any(c not in hexdigits for c in value[1:])
        ):
            raise ValueError("color must be #RRGGBB")
        try:
            return cls(*(int(value[i : i + 2], 16) for i in (1, 3, 5)))
        except ValueError as error:
            raise ValueError("color must be #RRGGBB") from error


@dataclass(frozen=True)
class Glow:
    color: Color = Color(255, 255, 255)
    blur: float = 0
    border: float = 0
    opacity: float = 1

    def __post_init__(self):
        _appearance_values(self.color, self.border, self.opacity)
        _finite(self.blur, "blur")
        if self.blur < 0:
            raise ValueError("blur cannot be negative")


def _appearance_values(color, border, opacity):
    if not isinstance(color, Color):
        raise TypeError("appearance colors must be Color values")
    _finite(border, "border")
    _finite(opacity, "opacity")
    if border < 0 or not 0 <= opacity <= 1:
        raise ValueError("border must be nonnegative and opacity must be in 0..1")


@dataclass(frozen=True)
class Paint:
    fill: Color = Color(255, 255, 255)
    outline: Color = Color(0, 0, 0)
    border: float = 0
    opacity: float = 1
    glow: Glow | None = None

    def __post_init__(self):
        _appearance_values(self.fill, self.border, self.opacity)
        if not isinstance(self.outline, Color) or (
            self.glow is not None and not isinstance(self.glow, Glow)
        ):
            raise ValueError("invalid outline or glow")


@dataclass(frozen=True)
class TrackPaint:
    track: HighlightTrack
    paint: Paint
    priority: int = 0

    def __post_init__(self):
        if type(self.priority) is not int:
            raise ValueError("track priority must be an integer")


@dataclass(frozen=True)
class PaintedRegion:
    unit_index: int
    region: Region
    paints: tuple[Paint, ...]


def compose_highlights(
    layers: tuple[TrackPaint, ...], time_ms: float, *, overlap: str
) -> tuple[PaintedRegion, ...]:
    """Resolve disjoint body regions; paints are ordered bottom to top.

    union requires identical appearance at overlaps. priority picks the highest
    priority and rejects conflicting ties. layer requires distinct priorities at
    overlaps and retains every paint, including intentional duplicate opacity.
    Before-singing paint is outside this operation and is drawn once per target.
    """
    if overlap not in {"union", "priority", "layer"}:
        raise ValueError("overlap must be union, priority or layer")
    if len({layer.track.id for layer in layers}) != len(layers):
        raise ValueError("duplicate track ids")
    _finite(time_ms, "time")
    result = []
    for unit_index in sorted({layer.track.unit_index for layer in layers}):
        coverage = [
            (region, layer)
            for layer in layers
            if layer.track.unit_index == unit_index
            for region in layer.track.regions_at(time_ms)
        ]
        boundaries = sorted(
            {x for region, _ in coverage for x in (region.left, region.right)}
        )
        for left, right in pairwise(boundaries):
            active = [
                layer
                for region, layer in coverage
                if region.left <= left and region.right >= right
            ]
            if not active:
                continue
            if overlap == "union":
                if len({layer.paint for layer in active}) != 1:
                    raise ValueError(
                        f"unit {unit_index}: union requires identical appearances"
                    )
                paints = (active[0].paint,)
            elif overlap == "priority":
                top = max(layer.priority for layer in active)
                choices = {layer.paint for layer in active if layer.priority == top}
                if len(choices) != 1:
                    raise ValueError(
                        f"unit {unit_index}: conflicting equal-priority appearances"
                    )
                paints = (next(iter(choices)),)
            else:
                if len({layer.priority for layer in active}) != len(active):
                    raise ValueError(
                        f"unit {unit_index}: layered highlights require distinct priorities"
                    )
                paints = tuple(
                    layer.paint
                    for layer in sorted(active, key=lambda layer: layer.priority)
                )
            if (
                result
                and result[-1].unit_index == unit_index
                and result[-1].region.right == left
                and result[-1].paints == paints
            ):
                previous = result.pop()
                left = previous.region.left
            result.append(PaintedRegion(unit_index, Region(left, right), paints))
    return tuple(result)
