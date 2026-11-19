"""Immutable color, paint and glow values in script pixels and RGB."""

from dataclasses import dataclass
from math import log, sqrt
from string import hexdigits
from typing import Self

from .timeline import _finite

_ASS_BLUR_TO_SIGMA = 2 / sqrt(log(256))


@dataclass(frozen=True)
class Color:
    """An immutable RGB color with integer channels in 0 through 255.

    hex accepts exactly #RRGGBB; ASS BGR conversion is performed at serialization
    boundaries.
    """

    red: int
    green: int
    blue: int

    def __post_init__(self) -> None:
        for channel in (self.red, self.green, self.blue):
            if type(channel) is not int or not 0 <= channel <= 255:
                raise ValueError("RGB channels must be integers in 0..255")

    @classmethod
    def hex(cls, value: str) -> Self:
        """Parse exactly #RRGGBB into validated integer RGB channels; reject malformed strings."""
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
    """A paint glow with RGB color, nonnegative blur/border in script pixels, and opacity in 0 through 1.

    It is separate from the body fill and outline.
    """

    color: Color = Color(255, 255, 255)
    blur: float = 0
    border: float = 0
    opacity: float = 1

    @classmethod
    def from_studio(cls, color: Color, *, radius: int, outline: float = 0, opacity: float = 1) -> Self:
        """Create a single-pass Karaoke Studio text halo in script pixels.

        radius is Studio's Gaussian standard deviation. outline is the distance
        the full hard outline extends beyond the glyph, including a secondary rim.
        A zero radius hides the halo.
        """
        if type(radius) is not int or radius < 0:
            raise ValueError("radius must be a nonnegative integer")
        _appearance_values(color, outline, opacity)
        if radius == 0:
            return cls(color, opacity=0)
        # Studio widens its centered pen by one radius before blurring.
        return cls(color, blur=radius / _ASS_BLUR_TO_SIGMA, border=outline + radius / 2,
                   opacity=opacity)

    def __post_init__(self) -> None:
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
    """Resolved fill, outline, border width, opacity, and optional glow for one drawing.

    Distances use script pixels and opacity uses 0 through 1.
    """

    fill: Color = Color(255, 255, 255)
    outline: Color = Color(0, 0, 0)
    border: float = 0
    opacity: float = 1
    glow: Glow | None = None

    def __post_init__(self) -> None:
        _appearance_values(self.fill, self.border, self.opacity)
        if not isinstance(self.outline, Color) or (
            self.glow is not None and not isinstance(self.glow, Glow)
        ):
            raise ValueError("invalid outline or glow")
