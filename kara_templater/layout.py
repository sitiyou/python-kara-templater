from __future__ import annotations

import re
from dataclasses import replace

from . import _metrics
from .ass import Line, Record, Style
from .model import Box, KaraokeLine, LaidOutLine, LaidOutSegment, LaidOutUnit

KARAOKE = re.compile(r"\\(kf|ko|k|K)(-?\d+)")
BLOCKS = re.compile(r"\{[^}]*\}|[^{}]+|[{}]")


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


def _raw_syllables(text):
    result = [Record(text="", text_stripped="", start_time=0, end_time=0, duration=0, tag="")]
    current = Record(text="", text_stripped="", start_time=0, duration=0, tag="\\k")
    drawing = 0

    def tags(value):
        if value:
            current.text += "{" + value + "}"

    for block in BLOCKS.findall(text):
        if block.startswith("{") and block.endswith("}"):
            inner = block[1:-1]
            offset = 0
            for match in KARAOKE.finditer(inner):
                tags(inner[offset : match.start()])
                start = current.start_time + current.duration
                if current.duration > 0 or current.text_stripped:
                    current.end_time = start
                    result.append(current)
                    current = Record(text="", text_stripped="", start_time=start)
                current.start_time = start
                current.duration = max(0, int(match[2]) * 10)
                current.tag = "\\kf" if match[1] == "K" else "\\" + match[1]
                offset = match.end()
            tags(inner[offset:])
            for match in re.finditer(r"\\p(\d+)(?!\d)", inner):
                drawing = int(match[1])
        else:
            current.text += block
            if not drawing:
                current.text_stripped += block
    current.end_time = current.start_time + current.duration
    result.append(current)
    return result


def split_karaoke(text: str) -> tuple[list[Record], list[Record]]:
    syllables, furigana = [], []
    inline_fx = ""
    for raw in _raw_syllables(text):
        match = re.search(r"\\-([^}\\]+)", raw.text)
        if match:
            inline_fx = match[1]
        match = re.fullmatch(r"([ \t]*)(.*?)([ \t]*)", raw.text_stripped, re.DOTALL)
        prespace, core, postspace = match.groups()
        continuation = core.startswith(("#", "＃")) and bool(syllables)
        highlight = Record(start_time=raw.start_time, end_time=raw.end_time, duration=raw.duration)
        if continuation:
            syl = syllables[-1]
            syl.duration += raw.duration
            syl.kdur = syl.duration / 10
            syl.end_time = raw.end_time
            syl.highlights.append(highlight)
        else:
            syl = Record(raw)
            syl.update(
                i=len(syllables),
                prespace=prespace,
                postspace=postspace,
                inline_fx=inline_fx,
                highlights=[highlight],
                furi=[],
                isfuri=False,
            )
            syllables.append(syl)
        base, separator, ruby = core.replace("｜", "|").partition("|")
        if separator:
            marker = ruby[:1]
            isbreak = marker in {"!", "！", "<", "＜"}
            if isbreak:
                ruby = ruby[1:]
            furi = Record(
                text=ruby,
                text_stripped=ruby,
                text_spacestripped=ruby,
                start_time=raw.start_time,
                end_time=raw.end_time,
                duration=raw.duration,
                kdur=raw.duration / 10,
                tag=raw.tag,
                i=syl.i,
                inline_fx=inline_fx,
                prespace="",
                postspace="",
                highlights=[highlight],
                isfuri=True,
                isbreak=isbreak,
                spillback=marker in {"<", "＜"},
                syl=syl,
            )
            furigana.append(furi)
            syl.furi.append(furi)
        if not continuation:
            syl.text_stripped = prespace + base + postspace
            syl.text_spacestripped = base
            syl.kdur = syl.duration / 10
    return syllables, furigana


def layout_line(
    source: KaraokeLine,
    *,
    style: Style,
    ruby_style: Style | None = None,
    resolution: tuple[int, int] = (1920, 1080),
) -> LaidOutLine:
    if min(resolution) <= 0:
        raise ValueError("resolution must be positive")
    line = Line(style=style.name)
    line.styleref = style
    line.kara, line.furi = [], []
    for unit in source.units:
        syl = Record(
            text_stripped=unit.text,
            text_spacestripped=unit.text,
            prespace="",
            postspace="",
            furi=[],
            isfuri=False,
        )
        for segment in unit.segments:
            if segment.ruby:
                furi = Record(
                    text_spacestripped=segment.ruby,
                    prespace="",
                    postspace="",
                    isbreak=not syl.furi,
                    spillback=True,
                    isfuri=True,
                )
                syl.furi.append(furi)
                line.furi.append(furi)
        line.kara.append(syl)
    styles = {style.name: style}
    if ruby_style is not None:
        styles[style.name + "-furigana"] = ruby_style
    _position(line, styles, Record(res_x=resolution[0], res_y=resolution[1], video_x_correct_factor=1))
    units = []
    for source_unit, syl in zip(source.units, line.kara, strict=True):
        box = Box(line.left + syl.left, line.top, syl.width, syl.height)
        weights = [text_extents(line.furistyle or style, s.ruby)[0] if s.ruby else 0 for s in source_unit.segments]
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
                Box(line.left + furi.left, line.top - furi.height, furi.width, furi.height)
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
            groups.append(Record(syls=[], furi=[], basewidth=0, furiwidth=0, spillback=False))
        group = groups[-1]
        group.syls.append(syl)
        group.furi.extend(syl.furi)
        group.basewidth += syl.prespacewidth + syl.width + syl.postspacewidth
        group.furiwidth += sum(f.width for f in syl.furi)
        group.spillback |= any(f.spillback for f in syl.furi)
    cursor, ruby_right = 0, None
    for group in groups:
        ruby_offset = (
            (group.basewidth - group.furiwidth) / 2 if group.spillback or group.furiwidth <= group.basewidth else 0
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


def preprocess(line: Line, styles: dict[str, Style], meta: Record) -> Line:
    if not styles:
        raise ValueError("No ASS styles found")
    line.styleref = styles.get(line.style, next(iter(styles.values())))
    line.duration = line.end_time - line.start_time
    line.kara, line.furi = split_karaoke(line.text)
    return _position(line, styles, meta)


def _position(line, styles, meta):
    line.text_stripped = "".join(s.text_stripped for s in line.kara)
    line.width, line.height, line.descent, line.extlead = text_extents(line.styleref, line.text_stripped)
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
        syl.width, syl.height, _, _ = text_extents(syl.style, syl.text_spacestripped)
        syl.width *= factor
        syl.prespacewidth = text_extents(syl.style, syl.prespace)[0] * factor
        syl.postspacewidth = text_extents(syl.style, syl.postspace)[0] * factor
    line.width = max(line.width, _layout(line.kara))
    for side in ("l", "r", "v"):
        setattr(
            line,
            "eff_margin_" + side,
            max(0, getattr(line, "margin_" + side)) or getattr(line.styleref, "margin_" + side),
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
        left = line.eff_margin_l + (meta.res_x - line.eff_margin_l - line.eff_margin_r - line.width) / 2
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
