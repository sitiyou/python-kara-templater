from typing import assert_type

from kara_templater import (
    BarsCue,
    CuedLyrics,
    CuePreset,
    Document,
    DocumentLyrics,
    LyricLayout,
    ObjectGroup,
    bind_lyric_cues,
    layout_document_lyrics,
)


def author(document: Document, record_index: int) -> ObjectGroup:
    assert_type(document.lyrics_at(record_index), DocumentLyrics)
    layout = layout_document_lyrics(document, record_index)
    assert_type(layout, LyricLayout)
    bound = bind_lyric_cues(layout, {"bars": CuePreset(factory=BarsCue())})
    assert_type(bound, CuedLyrics)
    assert_type(bound.group(), ObjectGroup)
    assert_type(layout.unit_group(0), ObjectGroup)
    return layout.group()
