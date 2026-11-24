"""Font and shaping measurements in script pixels."""

from .. import _metrics
from ..ass import Style


def text_extents(style: Style, text: str, *, palt: bool = False) -> tuple[float, float, float, float]:
    """Measure text using the native font/shaping environment and ASS style metrics.

    Return width, height, descent, and external leading in script pixels.
    Each line with glyph ink reserves style.outline on each side of its
    typographic box. Blank lines retain their font metrics. The result uses
    the widest line, the sum of line heights and the largest padded descent.
    Set outline to zero to measure native advances. Shadows are excluded.
    """
    return _metrics.text_extents(
        style.fontname,
        style.fontsize,
        int(style.bold),
        int(style.italic),
        style.scale_x,
        style.scale_y,
        style.spacing,
        style.encoding,
        text,
        0,
        palt,
        style.outline,
    )

