"""Typed extension factories and measured source ranges."""

from typing import assert_type

from kara_templater import (
    BarsCue,
    CueContent,
    CueContext,
    CueFactory,
    CuePreset,
    Document,
    ObjectGroup,
    PositionedText,
    TextLayout,
    TimedTextSpan,
    bind_cues,
    layout_document_text,
)


def custom(context: CueContext) -> CueContent:
    return BarsCue()(context)


def author(document: Document, record_index: int) -> ObjectGroup:
    factory: CueFactory = custom
    layout = layout_document_text(document, record_index)
    assert_type(layout, TextLayout)
    assert_type(layout.characters, tuple[PositionedText, ...])
    assert_type(layout.timing, tuple[TimedTextSpan, ...])
    bound = bind_cues(layout, {"custom": CuePreset(factory=factory)})
    assert_type(bound.text, TextLayout)
    assert_type(bound.independent, tuple[ObjectGroup, ...])
    return bound.group()
