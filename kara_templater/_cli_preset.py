"""Default CLI karaoke recipe, built solely from the common lyric frontend."""

from dataclasses import dataclass, replace
from typing import Literal

from .appearance import paint_pair_from_style
from .ass import Document, Line, Style
from .composition import Color, Paint
from .document_text import _packed_color
from .geometry import Region, Vec2
from .lyric_line import LyricLine, LyricRule
from .lyrics.highlights import (
    Highlight,
    HighlightArrival,
    HighlightPass,
    LyricHighlights,
)
from .lyrics.placement import Layout, LayoutContext, LineLayoutRequest, Placement
from .lyrics.tracks import (
    LyricScene,
    LyricSource,
    Track,
    _build_lyric_scene,
    _SourceById,
)
from .scene_animation import FadeIn, FadeOut, ScalePulse, StatePatch, TimeSpan


@dataclass(frozen=True, kw_only=True)
class _SourcePlacement(Layout):
    align: int
    left: int
    right: int
    vertical: int

    def allocate(
        self, lines: tuple[LineLayoutRequest, ...], context: LayoutContext
    ) -> tuple[Placement, ...]:
        region = context.region
        column, row = (self.align - 1) % 3, (self.align - 1) // 3
        result = []
        for line in lines:
            box = line.body_bounds or line.bounds
            x = (
                self.left
                if column == 0
                else region.width - self.right - box.width
                if column == 2
                else self.left + (region.width - self.left - self.right - box.width) / 2
            )
            y = (
                region.height - self.vertical - box.height
                if row == 0
                else self.vertical
                if row == 2
                else (region.height - box.height) / 2
            )
            result.append(
                Placement(
                    line.id,
                    Vec2(region.left + x - box.left, region.top + y - box.top),
                    line.requested_display,
                )
            )
        return tuple(result)


def _passes(line: LyricLine) -> tuple[Highlight, ...]:
    return tuple(
        Highlight(
            f"unit:{index}",
            index,
            tuple(
                HighlightPass(
                    TimeSpan(s.timing.start, s.timing.end),
                    Region(box.left, box.right),
                    round=i,
                )
                for i, s in enumerate(unit.segments)
            ),
            StatePatch(),
            repeat="reset",
        )
        for index, unit in enumerate(line.layout.lyrics.units)
        if unit.segments
        for box in (line.layout.body.range_bounds(unit.start, unit.end),)
    )


@dataclass(frozen=True)
class _Paint:
    before: Paint
    after: Paint

    def __call__(self, line: LyricLine) -> LyricLine:
        return LyricHighlights.from_timing(
            StatePatch(fill=self.after.fill, face_opacity=self.after.opacity),
            edge_duration=0,
            base_paint=StatePatch(fill=self.before.fill, face_opacity=self.before.opacity),
        )(line)


def _measurement_style(style: Style) -> Style:
    # The highlighting pass applies before/after face alpha after measurement.
    fields = dict(style.fields)
    for key, value in fields.items():
        if key.lower() in (
            "primarycolour",
            "secondarycolour",
            "outlinecolour",
        ):
            packed = _packed_color(value)
            fields[key] = f"&H00{packed & 0xFFFFFF:06X}"
    return replace(style, fields=fields)


def preset_scene(
    document: Document,
    *,
    owner: str,
    before: Color | None,
    after: Color | None,
    pulse: Literal["none", "char", "chars", "syllable"],
    fade_in: float,
    fade_out: float,
    preview: float,
    tail: float | None,
    styles: tuple[str, ...] | None,
) -> LyricScene:
    rules = []
    if fade_in:
        rules.append(LyricRule("line", "enter", FadeIn(), duration=fade_in))
    if fade_out:
        rules.append(LyricRule("line", "exit", FadeOut(), duration=fade_out))
    if pulse == "char":
        rules.append(
            LyricRule("character", HighlightArrival(highlights=_passes), ScalePulse())
        )
    elif pulse == "chars":
        rules.append(LyricRule("character", "timing", ScalePulse()))
    elif pulse == "syllable":
        rules.append(LyricRule("syllable", "timing", ScalePulse()))

    def build_tracks(doc: Document, sources: tuple[LyricSource, ...]) -> tuple[Track, ...]:
        tracks = []
        source_styles = doc._lyric_styles()
        measurement_styles = tuple(_measurement_style(s) for s in source_styles.values())
        for source in sources:
            if styles is not None and source.style not in styles:
                continue
            assert source.record_index is not None
            record = doc.records[source.record_index]
            assert isinstance(record, Line)
            style = source_styles["Default" if doc._imported else source.style]
            pair = paint_pair_from_style(style)
            base_paint = pair.before if before is None else replace(pair.before, fill=before)
            highlight_paint = pair.after if after is None else replace(pair.after, fill=after)
            tracks.append(
                Track(
                    id=source.id,
                    source=_SourceById(source.id),
                    layout=_SourcePlacement(
                        align=style.align,
                        left=style.margin_l if doc._imported else record.margin_l or style.margin_l,
                        right=style.margin_r if doc._imported else record.margin_r or style.margin_r,
                        vertical=style.margin_v if doc._imported else record.margin_v or style.margin_v,
                    ),
                    preview=preview,
                    tail=tail,
                    effects=(
                        *(tuple(rules)),
                        _Paint(base_paint, highlight_paint),
                    ),
                    styles=measurement_styles,
                )
            )
        return tuple(tracks)

    return _build_lyric_scene(document, build_tracks=build_tracks, owner=owner)
