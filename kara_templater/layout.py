from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from . import _metrics
from .ass import Line, Record, Style
from .model import Box, KaraokeLine, LaidOutLine, LaidOutSegment, LaidOutUnit

if TYPE_CHECKING:
    from ._legacy_layout import LegacyLine, LegacySyllable


class _Syllable(Record):
    furi: list[_Syllable]
    width: float
    height: float
    left: float
    right: float
    prespacewidth: float
    postspacewidth: float
    isbreak: bool
    spillback: bool


class _Group(Record):
    syls: list[_Syllable]
    furi: list[_Syllable]
    basewidth: float
    furiwidth: float
    spillback: bool


class _LayoutLine(Line):
    """Transient layout attributes, populated by _position."""

    styleref: Style
    furistyle: Style | None
    kara: list[_Syllable]
    furi: list[_Syllable]
    left: float
    top: float
    width: float
    height: float


def text_extents(style: Style, text: str) -> tuple[float, float, float, float]:
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


def layout_line(
    source: KaraokeLine,
    *,
    style: Style,
    ruby_style: Style | None = None,
    resolution: tuple[int, int] = (1920, 1080),
) -> LaidOutLine:
    if min(resolution) <= 0:
        raise ValueError("resolution must be positive")
    line = _LayoutLine(style=style.name)
    line.styleref = style
    line.kara, line.furi = [], []
    for unit in source.units:
        syl = _Syllable(
            text_stripped=unit.text,
            text_spacestripped=unit.text,
            prespace="",
            postspace="",
            furi=[],
            isfuri=False,
        )
        for segment in unit.segments:
            if segment.ruby:
                furi = _Syllable(
                    text_spacestripped=segment.ruby,
                    prespace="",
                    postspace="",
                    isbreak=not syl.furi and not unit.ruby_continuation,
                    spillback=True,
                    isfuri=True,
                )
                syl.furi.append(furi)
                line.furi.append(furi)
        line.kara.append(syl)
    styles = {style.name: style}
    if ruby_style is not None:
        styles[style.name + "-furigana"] = ruby_style
    _position(
        line,
        styles,
        Record(res_x=resolution[0], res_y=resolution[1], video_x_correct_factor=1),
    )
    units = []
    for source_unit, syl in zip(source.units, line.kara, strict=True):
        box = Box(line.left + syl.left, line.top, syl.width, syl.height)
        weights = [
            text_extents(line.furistyle or style, s.ruby)[0] if s.ruby else 0
            for s in source_unit.segments
        ]
        if not sum(weights):
            weights = [1] * len(weights)
        total = sum(weights)
        cursor = 0
        furis = iter(syl.furi)
        segments = []
        for segment, weight in zip(source_unit.segments, weights, strict=True):
            left = box.left + box.width * cursor / total
            cursor += weight
            right = box.left + box.width * cursor / total
            furi = next(furis) if segment.ruby else None
            ruby_box = (
                Box(
                    line.left + furi.left,
                    line.top - furi.height,
                    furi.width,
                    furi.height,
                )
                if furi is not None
                else None
            )
            segments.append(LaidOutSegment(segment, left, right, ruby_box))
        units.append(LaidOutUnit(source_unit, box, tuple(segments)))
    return LaidOutLine(Box(line.left, line.top, line.width, line.height), tuple(units))


def _horizontal(item, left):
    item.left = left
    item.center = left + item.width / 2
    item.right = left + item.width


def _layout(syllables):
    groups = []
    for syl in syllables:
        join = groups and syl.furi and groups[-1].furi and not syl.furi[0].isbreak
        if not join:
            groups.append(
                _Group(syls=[], furi=[], basewidth=0, furiwidth=0, spillback=False)
            )
        group = groups[-1]
        group.syls.append(syl)
        group.furi.extend(syl.furi)
        group.basewidth += syl.prespacewidth + syl.width + syl.postspacewidth
        group.furiwidth += sum(f.width for f in syl.furi)
        group.spillback |= any(f.spillback for f in syl.furi)
    cursor, ruby_right = 0, None
    for group in groups:
        ruby_offset = (
            (group.basewidth - group.furiwidth) / 2
            if group.spillback or group.furiwidth <= group.basewidth
            else 0
        )
        left = cursor
        if group.furi and ruby_right is not None:
            left = max(left, ruby_right - min(0, ruby_offset))
        cursor = left
        for syl in group.syls:
            _horizontal(syl, cursor + syl.prespacewidth)
            cursor = syl.right + syl.postspacewidth
        ruby_cursor = left + ruby_offset
        for furi in group.furi:
            _horizontal(furi, ruby_cursor)
            ruby_cursor = furi.right
        if group.furi:
            ruby_right = ruby_cursor
    return cursor


def _position(line, styles, meta):
    line.text_stripped = "".join(s.text_stripped for s in line.kara)
    line.width, line.height, line.descent, line.extlead = text_extents(
        line.styleref, line.text_stripped
    )
    factor = meta.video_x_correct_factor
    line.width *= factor
    if line.furi:
        name = line.styleref.name + "-furigana"
        if name not in styles:
            styles[name] = replace(
                line.styleref,
                name=name,
                fontsize=line.styleref.fontsize / 2,
                outline=line.styleref.outline / 2,
                shadow=line.styleref.shadow / 2,
            )
        line.furistyle = styles[name]
    else:
        line.furistyle = None
    for syl in [*line.kara, *line.furi]:
        syl.line = line
        syl.style = line.furistyle if syl.isfuri else line.styleref
        assert syl.style is not None
        syl.width, syl.height, _, _ = text_extents(syl.style, syl.text_spacestripped)
        syl.width *= factor
        syl.prespacewidth = text_extents(syl.style, syl.prespace)[0] * factor
        syl.postspacewidth = text_extents(syl.style, syl.postspace)[0] * factor
    line.width = max(line.width, _layout(line.kara))
    for side in ("l", "r", "v"):
        setattr(
            line,
            "eff_margin_" + side,
            max(0, getattr(line, "margin_" + side))
            or getattr(line.styleref, "margin_" + side),
        )
    line.eff_margin_t = line.eff_margin_b = line.eff_margin_v
    align = line.styleref.align
    if not 1 <= align <= 9:
        raise ValueError(f"Invalid alignment: {align}")
    horizontal = (align - 1) % 3
    vertical = (align - 1) // 3
    if horizontal == 0:
        left = line.eff_margin_l
    elif horizontal == 1:
        left = (
            line.eff_margin_l
            + (meta.res_x - line.eff_margin_l - line.eff_margin_r - line.width) / 2
        )
    else:
        left = meta.res_x - line.eff_margin_r - line.width
    _horizontal(line, left)
    line.halign = ("left", "center", "right")[horizontal]
    line.x = (line.left, line.center, line.right)[horizontal]
    if vertical == 0:
        line.top = meta.res_y - line.eff_margin_v - line.height
    elif vertical == 1:
        line.top = (meta.res_y - line.height) / 2
    else:
        line.top = line.eff_margin_v
    line.middle = line.top + line.height / 2
    line.bottom = line.top + line.height
    line.valign = ("bottom", "middle", "top")[vertical]
    line.y = (line.bottom, line.middle, line.top)[vertical]
    line.hcenter, line.vcenter = line.center, line.middle
    return line


def split_karaoke(text: str) -> tuple[list[LegacySyllable], list[LegacySyllable]]:
    """v0.1.0 splitting API; new scenes may use Document.text_at instead."""
    from ._legacy_layout import split_karaoke as legacy_split

    return legacy_split(text)


def preprocess(line: Line, styles: dict[str, Style], meta: Record) -> LegacyLine:
    """Explicit historical in-place preprocessing for Python templates."""
    from ._legacy_layout import preprocess as legacy_preprocess

    return legacy_preprocess(line, styles, meta)
