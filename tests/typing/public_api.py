"""Public values and results retain precise types across the authoring workflow."""

from typing import assert_type

from kara_templater import (
    RED,
    AssResult,
    BackRate,
    Color,
    Document,
    DocumentLyrics,
    EventOrigin,
    Line,
    LyricScene,
    Style,
    Track,
    build_lyric_scene,
    smooth_rate,
    there_and_back,
)


def values_and_render(document: Document, track: Track) -> None:
    assert_type(Color.hex("#112233"), Color)
    assert_type(RED, Color)
    assert_type(document.styles, dict[str, Style])
    assert_type(document.lines, list[Line])
    assert_type(document.dumps(), str)
    assert_type(Document.parse(document.dumps()), Document)
    assert_type(document.meta.res_x, int)
    assert_type(document.lyrics_at(0), DocumentLyrics)
    assert_type(smooth_rate(0.5), float)
    assert_type(there_and_back(0.5), float)
    assert_type(there_and_back(peak_at=0.2), BackRate)
    prepared = build_lyric_scene(document, tracks=(track,))
    assert_type(prepared, LyricScene)
    assert_type(prepared.ass.compile(), AssResult)
    assert_type(
        prepared.ass.compile().event_origins, tuple[tuple[Line, EventOrigin | None], ...]
    )
