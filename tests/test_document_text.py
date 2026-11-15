from dataclasses import replace

import pytest

from kara_templater import Color, Document, Line, Record, Style
from kara_templater.document_text import CueMarker


def document(text: str) -> Document:
    return Document(
        [
            Style(),
            Style(name="Alt", fields={"PrimaryColour": "&H0000FF00"}),
            Line(text=text),
        ],
        Record(),
    )


def test_lossless_colors_resets_and_unicode_ranges():
    text = r"{\k20\c&H0000FF&}春{\3c&H00FF00&}🌸{\rAlt}風{\c&HFF0000&}色{\c}戻{\r}白"
    doc = document(text)
    parsed = doc.text_at(2)
    assert parsed.original() == text
    assert doc.lines[0].text == text
    assert parsed.text == "春🌸風色戻白"
    assert [(run.start, run.end) for run in parsed.runs] == [
        (i, i + 1) for i in range(6)
    ]
    assert [run.appearance.primary for run in parsed.runs] == [
        Color(255, 0, 0),
        Color(255, 0, 0),
        Color(0, 255, 0),
        Color(0, 0, 255),
        Color(0, 255, 0),
        Color(255, 255, 255),
    ]
    assert parsed.runs[1].appearance.outline == Color(0, 255, 0)
    assert parsed.timing[0].seconds == 0.2
    parsed.require_supported()


def test_nested_transform_is_preserved_not_applied_as_static_color():
    text = r"{\t(0,400,\1c&H0000FF&\fscx150)\k30}X"
    parsed = document(text).text_at(2)
    assert parsed.original() == text
    assert parsed.runs[0].appearance.primary == Color(255, 255, 255)
    assert len(parsed.unsupported) == 1
    assert parsed.timing[0].seconds == 0.3
    with pytest.raises(ValueError, match="record 2, text offset 0"):
        parsed.require_supported()


def test_cues_have_no_text_or_timing_and_match_direct_construction():
    cue = CueMarker("intro one", "bars", 1, "independent")
    doc = document(r"{\k25}A" + cue.markup() + r"{\k0}B{\kt90\K10}C")
    parsed = doc.text_at(2)
    assert parsed.cues == (cue,)
    assert parsed.text == "ABC"
    assert [(tag.kind, tag.seconds, tag.offset) for tag in parsed.timing] == [
        ("k", 0.25, 0),
        ("k", 0, 1),
        ("kt", 0.9, 2),
        ("K", 0.1, 2),
    ]
    assert replace(cue, offset=0).markup() == cue.markup()


@pytest.mark.parametrize(
    "markup",
    [
        "{kara:v2 cue id=a preset=bars}",
        "{kara:v1 cue id=a preset=bars placement=bad}",
        "{kara:v1 cue id=a preset=bars id=b}",
        "{kara:v1 cue id=a}",
        "{kara:v1 cue id=a preset=bars extra=1}",
        "{kara:v1 cue id=a preset=bars}{kara:v1 cue id=a preset=bars}",
    ],
)
def test_invalid_cues_fail_with_source(markup: str):
    with pytest.raises(ValueError, match="record 2, text offset"):
        document(markup).text_at(2)


def test_literal_comments_and_escapes_roundtrip():
    text = r"a{ordinary comment}\Nb\hc"
    parsed = document(text).text_at(2)
    assert parsed.text == "a\nb\u00a0c"
    assert parsed.original() == text
    assert not parsed.cues


def test_missing_styles_and_wrong_records():
    with pytest.raises(TypeError, match="not an ASS event"):
        document("a").text_at(0)
    with pytest.raises(ValueError, match="unknown reset style"):
        document(r"{\rMissing}a").text_at(2)
    with pytest.raises(ValueError, match="unclosed block"):
        document("{a").text_at(2)


def test_soft_line_break_obeys_document_wrapstyle_without_losing_raw_text():
    doc = document(r"a\nb")
    assert doc.text_at(2).text == "a b"
    doc.meta["wrapstyle"] = "2"
    assert doc.text_at(2).text == "a\nb"
    assert doc.text_at(2).original() == r"a\nb"


@pytest.mark.parametrize(
    "identifier",
    ["intro one", "歌前🌸", "singer's cue", 'say "go"', "a=b;$(literal)", "a\tb"],
)
def test_cue_quoted_values_roundtrip_without_execution(identifier: str):
    cue = CueMarker(identifier, identifier, offset=2)
    raw = "🌸A" + cue.markup() + "B"
    parsed = document(raw).text_at(2)
    assert parsed.cues == (cue,)
    assert parsed.text == "🌸AB"
    assert parsed.original() == raw


@pytest.mark.parametrize(
    "block",
    [
        "kara:v1 unknown id=a preset=bars",
        "kara:v1 cue id='unclosed preset=bars",
        "kara:v1 cue id=a preset=bars missing_equals",
        "kara:v1 cue id=a preset=bars offset=3",
    ],
)
def test_cue_errors_report_raw_source_offset_after_unicode(block: str):
    prefix = r"{\k20}🌸"
    with pytest.raises(ValueError, match=rf"record 2, text offset {len(prefix)}:"):
        document(prefix + "{" + block + "}").text_at(2)


def test_cue_ids_are_scoped_to_source_record():
    marker = CueMarker("intro", "bars").markup()
    doc = document(marker + "A")
    doc.records.append(Line(text=marker + "B"))
    assert doc.text_at(2).cues == doc.text_at(3).cues


@pytest.mark.parametrize("character", ["{", "}", "\\", "\r", "\n"])
def test_cue_identifiers_cannot_escape_ass_comment_block(character: str):
    with pytest.raises(ValueError, match="identifiers"):
        CueMarker("intro" + character, "bars")
    with pytest.raises(ValueError, match="identifiers"):
        CueMarker("intro", "bars" + character)
