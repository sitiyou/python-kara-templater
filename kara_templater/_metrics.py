"""Font registration, text extents and positioned glyph outlines for authoring."""

from collections.abc import Iterable
from math import ceil, floor, inf, isfinite

from ._native_types import Outline
from ._text_native import add_font as add_font
from ._text_native import text_extents as text_extents
from ._text_native import text_shape as text_shape
from .geometry import Box


def stroke_bounds(outlines: Iterable[Outline], *, outer_radius: float) -> Box | None:
    """Bound round-stroke coverage in local script pixels relative to the first baseline.

    Pass the positioned outlines from text_shape and the largest outward radius
    over the desired interval and layers. The box includes the Bézier control
    hull and one pixel for shader antialiasing, rounded out to pixel boundaries.
    Empty ink (including whitespace) has no paint box. Layout advances, blur,
    shadows and subsequent scene transforms are measured separately.
    """
    if not isfinite(outer_radius) or outer_radius < 0:
        raise ValueError("outer_radius must be finite and nonnegative")
    left = top = inf
    right = bottom = -inf
    for points, _, _, _ in outlines:
        for x, y in points:
            left = min(left, x)
            right = max(right, x)
            top = min(top, y)
            bottom = max(bottom, y)
    if left == inf:
        return None
    padding = outer_radius + 1
    x_min, y_min = floor(left - padding), floor(top - padding)
    return Box(x_min, y_min, ceil(right + padding) - x_min, ceil(bottom + padding) - y_min)
