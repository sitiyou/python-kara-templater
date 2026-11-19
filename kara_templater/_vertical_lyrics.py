"""Studio vertical glyph geometry in script pixels."""

from dataclasses import replace
from itertools import groupby

from . import _metrics
from .geometry import Vec2
from .model import Box
from .scene_lyrics import LyricLayout, PositionedRuby
from .scene_text import PositionedText, _union
from .text_geometry import _VectorGuideText

_ROTATED = frozenset("ーｰ—―‐‑‒–〜～→←（）()「」『』【】〔〕［］｛｝〈〉《》[]{}<>")
_SMALL_KANA = frozenset("ぁぃぅぇぉっゃゅょゎァィゥェォッャュョヮヵヶ")


def _advance(item: PositionedText, text: str) -> float:
    node = item.object
    state = node.state
    return _metrics.text_extents(
        node.font,
        node.font_size,
        int(node.bold),
        int(node.italic),
        state.scale.x * 100,
        state.scale.y * 100,
        node.spacing,
        node.encoding,
        text.replace("\\", "\\\u2060"),
    )[0]


def _vertical_glyph(item: PositionedText, cell: Box) -> PositionedText:
    """Center the pen or guide in its cell and carry its ink into column coordinates."""
    node = item.object
    state = node.state
    ink = item.ink_bounds
    angle = 0
    if isinstance(node, _VectorGuideText) and ink is not None:
        origin = state.position + Vec2(
            cell.center - ink.center, cell.middle - ink.middle
        )
    else:
        advance = _advance(item, node.text)
        baseline = (item.baseline or 0) * state.scale.y
        origin = Vec2(
            cell.center - round(advance) / 2, cell.top + round(baseline) - baseline
        )
        if node.text in _ROTATED:
            angle = 90
            pivot = Vec2(cell.center, cell.middle)
            origin = pivot + (origin - pivot).rotated(angle)
        else:
            shift = (
                0.28
                if node.text in ("、", "。", "，", "．")
                else 0.10
                if node.text in _SMALL_KANA
                else 0
            )
            origin += Vec2(cell.width * shift, -cell.height * shift)

    if ink is not None:
        # A quarter turn preserves axis alignment, so two opposite corners suffice.
        first = origin + (Vec2(ink.left, ink.top) - state.position).rotated(angle)
        last = origin + (
            Vec2(ink.right, ink.top + ink.height) - state.position
        ).rotated(angle)
        ink = Box(
            min(first.x, last.x),
            min(first.y, last.y),
            abs(last.x - first.x),
            abs(last.y - first.y),
        )
    return replace(
        item,
        bounds=cell,
        ink_bounds=ink,
        object=replace(node, state=replace(state, position=origin, rotation=angle)),
    )


def _vertical_from_font(layout: LyricLayout, ruby_gap: float) -> LyricLayout:
    if not layout.body.characters:
        return replace(layout, _vertical=True)
    host = layout.body.characters[0]
    ascent = (host.baseline or 0) * host.object.state.scale.y
    height = max(1, round(ascent) + round(host.bounds.height - ascent))
    width = round(_advance(host, "永")) or height
    reading = next((g for r in layout.ruby for g in r.layout.characters), None)
    ruby_width = (
        (round(_advance(reading, "永")) or round(reading.bounds.height))
        if reading
        else 0
    )
    return _vertical_line(
        layout,
        cell_width=width,
        cell_height=height,
        ruby_width=ruby_width,
        ruby_gap=ruby_gap,
    )


def _vertical_line(
    layout: LyricLayout,
    *,
    cell_width: int,
    cell_height: int,
    ruby_width: int,
    ruby_gap: float,
) -> LyricLayout:
    """Reflow a measured line around x=0, from y=0 downward, retaining source ranges and clocks."""
    body = tuple(
        _vertical_glyph(
            item, Box(-cell_width / 2, i * cell_height, cell_width, cell_height)
        )
        for i, item in enumerate(layout.body.characters)
    )
    body_bounds = _union(tuple(item.bounds for item in body))
    readings: list[PositionedRuby] = []
    ruby_x = round((cell_width + ruby_width) / 2 + ruby_gap)
    for (start, end), group in groupby(
        layout.ruby, key=lambda r: (r.body_start, r.body_end)
    ):
        parts = tuple(group)
        hosts = [item.bounds for item in body if item.start < end and start < item.end]
        count = sum(len(part.layout.characters) for part in parts)
        if not hosts or not count:
            readings.extend(parts)
            continue
        top = hosts[0].top
        step = (hosts[-1].top + cell_height - top) / count
        index = 0
        for part in parts:
            items = tuple(
                _vertical_glyph(
                    item,
                    Box(
                        ruby_x - ruby_width / 2,
                        round(top + (index + j) * step),
                        ruby_width,
                        max(1, round(step)),
                    ),
                )
                for j, item in enumerate(part.layout.characters)
            )
            index += len(items)
            readings.append(
                replace(
                    part,
                    layout=replace(
                        part.layout,
                        characters=items,
                        bounds=_union(tuple(item.bounds for item in items)),
                    ),
                )
            )
    return replace(
        layout,
        body=replace(layout.body, characters=body, bounds=body_bounds),
        ruby=tuple(readings),
        _vertical=True,
        bounds=_union((body_bounds, *(r.layout.bounds for r in readings))),
    )
