from . import _metrics
from .ass import Style


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


def _ruby_group(
    body: float, reading: float, spillback: bool, previous: float | None,
) -> tuple[float, float, float | None]:
    """Return body shift, reading offset and carried spill, as in karaskel.do_furigana_layout."""
    if not reading:
        return 0, 0, previous - body if previous is not None and previous > 0 else None
    shift = max(0.0, previous or 0.0)
    excess = reading - body
    if excess <= 0:
        return shift, -excess / 2, excess / 2
    if spillback:
        # Lua distinguishes an absent spill from zero (a flush preceding annotation).
        return shift + (excess / 2 if previous is not None else 0), -excess / 2, excess / 2
    return shift, 0, excess
