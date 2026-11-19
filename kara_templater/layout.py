from __future__ import annotations

from dataclasses import dataclass, replace

from . import _metrics
from .ass import Style
from .model import Box, KaraokeLine, LaidOutLine, LaidOutSegment, LaidOutUnit, TextUnit


def text_extents(style: Style, text: str) -> tuple[float, float, float, float]:
    """Measure text using the native font/shaping environment and ASS style metrics.

    Return width, height, descent, and external leading in script pixels.
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
    )


@dataclass
class _MeasuredUnit:
    source: TextUnit
    width: float
    height: float
    readings: tuple[Box | None, ...]
    left: float = 0
    ruby_left: float = 0

    def place(self, line: Box) -> LaidOutUnit:
        box = Box(line.left + self.left, line.top, self.width, self.height)
        weights = [reading.width if reading else 0.0 for reading in self.readings]
        if not any(weights):
            weights = [1.0] * len(weights)
        total = sum(weights)
        cursor = 0.0
        ruby_cursor = self.ruby_left
        segments = []
        for segment, reading, weight in zip(
            self.source.segments, self.readings, weights, strict=True
        ):
            left = box.left + box.width * cursor / total
            cursor += weight
            right = box.left + box.width * cursor / total
            if reading:
                reading = replace(
                    reading, left=line.left + ruby_cursor, top=line.top - reading.height
                )
                ruby_cursor += reading.width
            segments.append(LaidOutSegment(segment, left, right, reading))
        return LaidOutUnit(self.source, box, tuple(segments))


def _measure(style: Style, text: str) -> Box:
    width, height, _, _ = text_extents(style, text)
    return Box(0, 0, width, height)


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


def layout_line(
    source: KaraokeLine,
    *,
    style: Style,
    ruby_style: Style | None = None,
    resolution: tuple[int, int] = (1920, 1080),
) -> LaidOutLine:
    """Measure a structured KaraokeLine with body and reading styles at the requested resolution.

    Return layout boxes without changing source singing intervals.
    """
    if min(resolution) <= 0:
        raise ValueError("resolution must be positive")
    if not 1 <= style.align <= 9:
        raise ValueError(f"Invalid alignment: {style.align}")
    if ruby_style is None:
        ruby_style = replace(style, fontsize=style.fontsize / 2)

    groups: list[list[_MeasuredUnit]] = []
    for unit in source.units:
        body = _measure(style, unit.text)
        readings = tuple(
            _measure(ruby_style, part.ruby) if part.ruby else None
            for part in unit.segments
        )
        if not (
            groups
            and unit.ruby_continuation
            and any(readings)
            and any(groups[-1][-1].readings)
        ):
            groups.append([])
        groups[-1].append(_MeasuredUnit(unit, body.width, body.height, readings))

    cursor = 0.0
    spill: float | None = None
    for group in groups:
        body_width = sum(unit.width for unit in group)
        readings = [r for unit in group for r in unit.readings if r is not None]
        extra, offset, spill = _ruby_group(
            body_width, sum(r.width for r in readings),
            any(u.source.ruby_spillback and any(u.readings) for u in group), spill,
        )
        cursor += extra
        ruby_cursor = cursor + offset
        for unit in group:
            unit.left = cursor
            unit.ruby_left = ruby_cursor
            cursor += unit.width
            ruby_cursor += sum(r.width for r in unit.readings if r is not None)

    full = _measure(style, "".join(unit.text for unit in source.units))
    width = max(full.width, cursor)
    available = resolution[0] - style.margin_l - style.margin_r - width
    left = style.margin_l + available * ((style.align - 1) % 3) / 2
    top = (
        resolution[1] - style.margin_v - full.height,
        (resolution[1] - full.height) / 2,
        style.margin_v,
    )[(style.align - 1) // 3]
    line = Box(left, top, width, full.height)
    return LaidOutLine(
        line, tuple(unit.place(line) for group in groups for unit in group)
    )
