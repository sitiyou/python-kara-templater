"""Public document binding contracts remain concrete for extension authors."""

from typing import assert_type

from kara_templater import (
    Color,
    CueMarker,
    Document,
    DocumentText,
    SingingTag,
    TextAppearance,
    TextIssue,
    TextRun,
    TextToken,
)


def inspect_text(document: Document, record_index: int) -> None:
    bound = document.text_at(record_index)
    assert_type(bound, DocumentText)
    assert_type(bound.tokens, tuple[TextToken, ...])
    assert_type(bound.runs, tuple[TextRun, ...])
    assert_type(bound.timing, tuple[SingingTag, ...])
    assert_type(bound.cues, tuple[CueMarker, ...])
    assert_type(bound.unsupported, tuple[TextIssue, ...])
    for run in bound.runs:
        assert_type(run.appearance, TextAppearance)
        assert_type(run.appearance.primary, Color)
    for cue in bound.cues:
        assert_type(cue.markup(), str)
