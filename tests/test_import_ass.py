from dataclasses import replace

import pytest
from source_assertions import require_origin

from kara_templater import (
    Body,
    Color,
    Document,
    Effect,
    ImportSettings,
    Line,
    Lyrics,
    Ruby,
    Segment,
    Style,
    import_karaoke,
    paint_pair_from_style,
    parse_karaoke,
    render_karaoke,
)
from kara_templater.ass import EVENT_FORMAT, STYLE_FORMAT


class ImportedLyrics(Effect):
    def compose(self):
        yield Lyrics(Body(), Ruby())

    def configure(self):
        self.text.sweep()


def document(*lines):
    return Document.parse(
        "[Script Info]\nPlayResX: 640\nPlayResY: 480\n[V4+ Styles]\nFormat: "
        + STYLE_FORMAT
        + "\n"
        + Style(fontname="DejaVu Sans", fontsize=32).serialize()
        + "\n[Events]\nFormat: "
        + EVENT_FORMAT
        + "\n"
        + "\n".join(line.serialize() for line in lines)
    )


def lyric(text=r"{\k20}A{\k30}B", **kwargs):
    return Line(text=text, start_time=1000, end_time=2000, **kwargs)


def test_import_failure_identifies_actual_record_without_inventing_segment():
    from kara_templater import AssImportError

    source = document(lyric(), lyric(r"{\k20\blur4}B"))
    original = source.dumps()
    index = next(
        i
        for i, r in enumerate(source.records)
        if isinstance(r, Line) and "blur" in r.text
    )
    with pytest.raises(AssImportError, match="unsupported ASS override") as caught:
        render_karaoke(source, effect=ImportedLyrics())
    error = caught.value
    assert error.record_index == index
    assert source.records[error.record_index].text == r"{\k20\blur4}B"
    assert error.style == "Default"
    assert require_origin(error).effect == "ASS import"
    assert require_origin(error).sources[0].item_id.startswith("ass:")
    assert require_origin(error).sources[0].unit_index is None
    assert isinstance(error.__cause__, ValueError)
    assert source.dumps() == original


@pytest.mark.parametrize("suffix", ["missing-separator", ":original"])
def test_invalid_owned_source_marker_reports_record_without_false_id(suffix):
    from kara_templater import AssImportError

    source = document(lyric(comment=True, effect="karaoke:source:v1:default:" + suffix))
    with pytest.raises(AssImportError) as caught:
        import_karaoke(source)
    error = caught.value
    assert source.records[error.record_index].comment
    assert error.origin is None


def test_timing_tags_offsets_static_prefix_and_ruby_continuation():
    parsed = parse_karaoke(lyric(r"pre{\K20}漢|かん{\kt50\ko10}＃|じ{\kf0}字"))
    assert parsed.units[0].text == "pre" and not parsed.units[0].segments
    assert parsed.units[1].text == "漢"
    assert parsed.units[1].segments == (
        Segment(1000, 1200, "かん"),
        Segment(1500, 1600, "じ"),
    )
    assert parsed.units[2].segments == (Segment(1600, 1600),)


def test_empty_timed_chunks_consume_time_and_hard_spaces_remain():
    units = parse_karaoke(lyric(r"{\k10\k20}A\hB")).units
    assert units[0].text == ""
    assert units[1].text == "A\u00a0B"
    assert units[1].segments == (Segment(1100, 1300),)


@pytest.mark.parametrize(
    "text",
    [
        r"{\k20\i1}A",
        r"{\k-2}A",
        r"{\k20}A{\kt10\k20}B",
        r"{\k20}#",
        r"{\k20}A\NB",
        r"{\k20}A|a|b",
        r"{\k20A",
    ],
)
def test_invalid_or_unsupported_input_has_event_context(text):
    with pytest.raises(ValueError, match=r"event \d+ \(Default\)"):
        import_karaoke(document(lyric(text)))


def test_auto_render_preserves_sources_and_can_reimport_saved_output():
    source = document(
        lyric(effect="original:effect"),
        Line(text="plain subtitle", start_time=0, end_time=3000),
        lyric(comment=True, effect="notes"),
    )
    original = source.dumps()
    result = render_karaoke(source, effect=ImportedLyrics(), owner="a:b%")
    assert source.dumps() == original
    marked = [
        line
        for line in result.document.lines
        if line.effect.startswith("karaoke:source:v1:")
    ]
    assert len(marked) == 1 and marked[0].comment
    assert marked[0].text == source.lines[0].text
    imported = import_karaoke(Document.parse(result.document.dumps()), owner="a:b%")
    assert imported.sources[0].original_effect == "original:effect"
    again = render_karaoke(
        Document.parse(result.document.dumps()), effect=ImportedLyrics(), owner="a:b%"
    )
    assert again.document.dumps() == result.document.dumps()
    assert any(
        line.text == "plain subtitle" and not line.comment
        for line in again.document.lines
    )
    assert any(line.effect == "notes" and line.comment for line in again.document.lines)


def test_identical_sources_get_distinct_stable_ids():
    imported = import_karaoke(document(lyric(), lyric()))
    assert len({item.id for item in imported.items}) == 2
    result = render_karaoke(document(lyric(), lyric()), effect=ImportedLyrics())
    assert tuple(item.id for item in import_karaoke(result.document).items) == tuple(
        item.id for item in imported.items
    )


def test_windows_margins_and_style_selection():
    imported = import_karaoke(
        document(lyric(margin_l=50, margin_v=20)), settings=ImportSettings(2000, 250)
    )
    assert imported.items[0].window.start_ms == 0
    assert imported.items[0].window.end_ms == 2250
    assert imported.items[0].margins == (50, 0, 20)
    assert not import_karaoke(
        document(lyric()), settings=ImportSettings(styles=("Other",))
    ).items


def test_style_palette_decodes_bgr_and_secondary_before_primary():
    style = Style(
        fields={
            "PrimaryColour": "&H00112233",
            "SecondaryColour": "&H00445566",
            "OutlineColour": "&H00010203",
        }
    )
    pair = paint_pair_from_style(style)
    assert pair.after.fill == Color(0x33, 0x22, 0x11)
    assert pair.before.fill == Color(0x66, 0x55, 0x44)
    assert pair.after.outline == Color(3, 2, 1)
    with pytest.raises(ValueError, match="invalid PrimaryColour"):
        paint_pair_from_style(replace(style, fields={"PrimaryColour": "nonsense"}))
