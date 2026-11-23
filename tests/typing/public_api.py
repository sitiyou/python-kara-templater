"""Public values and results retain precise types across the authoring workflow."""

from collections.abc import Iterator
from typing import assert_type

from kara_templater import (
    RED,
    BackRate,
    Color,
    Document,
    EventOrigin,
    KaraokeItem,
    KaraokeLine,
    Line,
    LyricScene,
    SceneResult,
    Segment,
    SourceRef,
    Style,
    TextUnit,
    Track,
    import_karaoke,
    layout_line,
    parse_karaoke,
    prepare_tracks,
    smooth_rate,
    there_and_back,
    walk_karaoke,
)


def values_and_render(document: Document, item: KaraokeItem, track: Track) -> None:
    assert_type(Color.hex("#112233"), Color)
    assert_type(RED, Color)
    assert_type(document.styles, dict[str, Style])
    assert_type(document.lines, list[Line])
    assert_type(document.dumps(), str)
    assert_type(Document.parse(document.dumps()), Document)
    assert_type(document.meta.res_x, int)
    assert_type(parse_karaoke(Line()), KaraokeLine)
    assert_type(import_karaoke(document).items, tuple[KaraokeItem, ...])
    assert_type(walk_karaoke((item,)), Iterator[tuple[SourceRef, Segment]])
    assert_type(
        walk_karaoke((item,), level="unit"), Iterator[tuple[SourceRef, TextUnit]]
    )
    assert_type(
        walk_karaoke((item,), level="line"), Iterator[tuple[SourceRef, KaraokeLine]]
    )
    assert_type(smooth_rate(0.5), float)
    assert_type(there_and_back(0.5), float)
    assert_type(there_and_back(peak_at=0.2), BackRate)
    prepared = prepare_tracks(document, tracks=(track,))
    assert_type(prepared, LyricScene)
    assert_type(prepared.ass.compile(), SceneResult)
    assert_type(
        prepared.ass.compile().event_origins, tuple[tuple[Line, EventOrigin | None], ...]
    )
    assert_type(layout_line(item.source, style=Style()).box.width, float)
