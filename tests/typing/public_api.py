"""Public values and results retain precise types across the authoring workflow."""

from collections.abc import Iterator
from typing import assert_type

from kara_templater import (
    RED,
    Color,
    Contextual,
    Document,
    EventOrigin,
    HighlightAnimation,
    KaraokeItem,
    KaraokeLine,
    Line,
    PropertyContext,
    Scene,
    SceneResult,
    Segment,
    SourceRef,
    Style,
    TextUnit,
    TimeRef,
    Track,
    Transition,
    display,
    import_karaoke,
    layout_line,
    parse_karaoke,
    prepare_tracks,
    singing,
    smooth,
    there_and_back,
    walk_karaoke,
)
from kara_templater.properties import BackRate


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
    assert_type(singing.start + 100, TimeRef)
    assert_type(display.start, TimeRef)
    assert_type(smooth(0.5), float)
    assert_type(there_and_back(0.5), float)
    assert_type(there_and_back(peak_at=0.2), BackRate)
    assert_type(Transition(1, 1.2, rate=lambda p: assert_type(p, float))(0.5), float)
    assert_type(
        Contextual(lambda ctx: assert_type(ctx, PropertyContext).progress), Contextual
    )
    assert_type(
        HighlightAnimation(offset_y=lambda p: assert_type(p, float)), HighlightAnimation
    )
    prepared = prepare_tracks(document, tracks=(track,))
    assert_type(prepared.scene, Scene)
    assert_type(prepared.compile(), SceneResult)
    assert_type(
        prepared.compile().event_origins, tuple[tuple[Line, EventOrigin | None], ...]
    )
    assert_type(layout_line(item.source, style=Style()).box.width, float)
