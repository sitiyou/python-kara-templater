from dataclasses import replace
from math import ceil, floor

import pytest

from kara_templater import (
    Color,
    CueMarker,
    Document,
    Lifetime,
    Line,
    Style,
    layout_document_lyrics,
    layout_document_text,
    parse_document_lyrics,
)
from kara_templater.characters import LayoutCapabilityError


def document(text):
    doc = Document.create(
        styles=(Style(fontname="DejaVu Sans", fontsize=64, shadow=0),)
    )
    doc.records.append(Line(text=text, start_time=1000, end_time=4000))
    return doc, len(doc.records) - 1


def test_projection_preserves_original_color_ranges_and_repeated_timing():
    doc, index = document(
        r"{\k20\1c&H0000FF&}AB|ab{\k0}#|!c{\kt100\k30}#|<d{\k50\1c}C|c"
    )
    raw = doc.text_at(index)
    lyrics = parse_document_lyrics(raw, start=1)
    assert lyrics.source.original() == doc.lines[0].text
    assert lyrics.body.text == "ABC"
    assert [(u.start, u.end) for u in lyrics.units] == [(0, 2), (2, 3)]
    segments = lyrics.units[0].segments
    assert [(s.singing.start, s.singing.end) for s in segments] == [
        (1, 1.2),
        (1.2, 1.2),
        (2, 2.3),
    ]
    assert [s.ruby.source.text for s in segments if s.ruby is not None] == [
        "ab",
        "c",
        "d",
    ]
    assert [s.ruby.mode for s in segments if s.ruby is not None] == [
        "join",
        "break",
        "spill",
    ]
    for mapping in lyrics.mapping:
        assert (
            raw.text[mapping.source_start : mapping.source_end]
            == lyrics.body.text[mapping.start : mapping.end]
        )
    assert lyrics.body.runs[0].appearance.primary == Color(255, 0, 0)
    assert lyrics.body.runs[-1].appearance.inline_colors == frozenset()


def test_untimed_prefix_and_kt_gap_are_not_discarded():
    doc, index = document(r"pre{\k10}A{\kt50}gap{\k20}B{\kt100}tail")
    lyrics = parse_document_lyrics(doc.text_at(index), start=1)
    assert lyrics.body.text == "preAgapBtail"
    assert [lyrics.body.text[u.start : u.end] for u in lyrics.units] == [
        "pre",
        "A",
        "gap",
        "B",
        "tail",
    ]
    assert [len(u.segments) for u in lyrics.units] == [0, 1, 0, 1, 0]


def test_cue_anchors_project_to_body_and_ruby_anchors_fail():
    marker = CueMarker("cue", "bars").markup()
    doc, index = document(r"{\k20}A|aa" + marker + r"{\k20}B|bb")
    assert parse_document_lyrics(doc.text_at(index), start=1).body.cues[0].offset == 1
    doc, index = document(r"{\k20}A|a" + marker + "a")
    with pytest.raises(ValueError, match="inside ruby"):
        parse_document_lyrics(doc.text_at(index), start=1)


@pytest.mark.parametrize(
    "text", ["A|a", r"{\k20}#|a", r"{\k20}A|a|b", r"{\k20}|a", r"{\k20}#junk"]
)
def test_malformed_lyric_syntax_has_diagnostics(text):
    doc, index = document(text)
    with pytest.raises(ValueError):
        parse_document_lyrics(doc.text_at(index), start=1)


def test_ruby_style_defaults_inline_precedence_and_reset():
    doc, index = document(r"{\k20}A|a{\k20\1c&HFFFFFF&}B|b{\k20\1c}C|c")
    ruby_style = Style(
        name="Default-furigana",
        fontname="DejaVu Sans",
        fontsize=24,
        shadow=0,
        fields={
            "PrimaryColour": "&H000000FF",
            "OutlineColour": "&H00000000",
            "BackColour": "&H00000000",
        },
    )
    doc.records.insert(index, ruby_style)
    index += 1
    before = doc.dumps()
    layout = layout_document_lyrics(doc, index, display=Lifetime(0, 5))
    colors = [ruby.layout.characters[0].object.state.fill for ruby in layout.ruby]
    assert colors == [Color(255, 0, 0), Color(255, 255, 255), Color(255, 0, 0)]
    assert all(r.layout.characters[0].object.font_size == 24 for r in layout.ruby)
    assert [t for s in layout.body.singing for t in (s.start, s.end)] == pytest.approx(
        [1, 1.2, 1.2, 1.4, 1.4, 1.6]
    )
    assert all(
        item.object.lifetime == Lifetime(0, 5) for item in layout.body.characters
    )
    assert doc.dumps() == before


def test_whole_body_shaping_and_unit_pivot_keep_ruby_relative():
    plain, index = document("AV")
    reference = layout_document_text(plain, index)
    doc, index = document(r"{\k20}A|a{\k20}V|v")
    layout = layout_document_lyrics(doc, index)
    assert layout.body.bounds.width == reference.bounds.width
    assert [i.bounds.left for i in layout.body.characters] == [
        i.bounds.left for i in reference.characters
    ]
    group = layout.unit_group(0)
    for child in group.children:
        assert child.origin is not None
        assert child.origin.sources[0].unit_index == 0
        original = next(
            item.object
            for item in (*layout.body.characters, *layout.ruby[0].layout.characters)
            if item.object.id == child.id
        )
        assert child.state.position + group.state.position == original.state.position
    assert layout.bounds.top < layout.body.bounds.top


@pytest.mark.parametrize("gap", [0, 3, 6])
def test_wide_ruby_breaks_reserve_space_without_changing_times(gap):
    doc, index = document(r"{\k20}A|!long{\k20}B|!word")
    layout = layout_document_lyrics(doc, index, ruby_gap=gap)
    first, second = layout.ruby
    assert second.layout.bounds.left >= first.layout.bounds.right
    body = layout.body.characters[1]
    assert body.ink_bounds is not None
    base_top = body.ink_bounds.top - body.object.state.border
    reading_bottom = max(
        c.ink_bounds.top + c.ink_bounds.height + c.object.state.border
        for c in second.layout.characters
        if c.ink_bounds is not None
    )
    assert base_top - reading_bottom == pytest.approx(gap)
    assert (
        layout.body.characters[1].bounds.left > layout.body.characters[0].bounds.right
    )
    assert layout.body.singing[1].start == 1.2


def test_ligature_across_syllables_is_preserved_until_split_requested():
    doc, index = document(r"{\k20}f{\k20}fi")
    layout = layout_document_lyrics(doc, index)
    assert layout.body.source.text == "ffi"
    assert len(layout.body.characters) == 1
    with pytest.raises(LayoutCapabilityError, match="cluster"):
        layout.unit_group(0)
    # Equal explicit colors may have different provenance without breaking shaping.
    doc, index = document(r"{\k20}f{\1c&HFFFFFF&}fi")
    assert len(layout_document_lyrics(doc, index).body.characters) == 1


def test_named_style_reset_changes_ruby_font_but_not_body_scope():
    doc, index = document(r"{\k20}A|a{\k20\rOther}B|b")
    doc.records.insert(index, replace(doc.styles["Default"], name="Other", fontsize=80))
    layout = layout_document_lyrics(doc, index + 1)
    assert [r.layout.characters[0].object.font_size for r in layout.ruby] == [32, 40]


def test_zero_and_centisecond_syllables_keep_exact_original_intervals():
    doc, index = document(r"{\k0}A{\k1}B{\k0}#{\kt10\k1}C")
    before = doc.dumps()
    layout = layout_document_lyrics(doc, index, display=Lifetime(0, 5))
    assert [
        time for span in layout.body.singing for time in (span.start, span.end)
    ] == pytest.approx([1, 1, 1, 1.01, 1.01, 1.01, 1.1, 1.11])
    assert layout.body.source.text == "ABC"
    assert len(layout.lyrics.units[1].segments) == 2
    assert doc.dumps() == before


def test_reversed_singing_cursor_identifies_document_record_and_decoded_offset():
    doc, index = document(r"{\k20}A{\kt10\k10}B")
    with pytest.raises(
        ValueError, match=rf"record {index}, decoded text offset 1: kt reverses"
    ):
        layout_document_lyrics(doc, index)


def test_shaping_error_after_style_reset_reports_document_range_and_cause():
    doc, index = document(r"A{\rOther}👩‍💻")
    doc.records.insert(index, replace(doc.styles["Default"], name="Other", fontsize=80))
    index += 1
    with pytest.raises(
        LayoutCapabilityError,
        match=rf"record {index}, decoded text range 1:4, style 'Other'",
    ) as caught:
        layout_document_lyrics(doc, index)
    assert isinstance(caught.value.__cause__, LayoutCapabilityError)
    assert "unit 0" in str(caught.value.__cause__)


def test_studio_cells_keep_explicit_tracking_between_clusters_and_ink_timed():
    def measured(spacing):
        doc = Document.create(styles=(
            Style(fontname="DejaVu Sans", fontsize=48, outline=3, spacing=spacing),
        ))
        doc.records.append(Line(text=r"{\k50}M{\k50} {\k50}i", start_time=0, end_time=1500))
        return layout_document_lyrics(doc, len(doc.records) - 1, studio_spacing=True).body

    plain, tracked = measured(0), measured(4)
    assert tracked.bounds.width == pytest.approx(plain.bounds.width + 8)
    for index, (original, moved) in enumerate(zip(plain.characters, tracked.characters, strict=True)):
        assert moved.bounds.left == pytest.approx(original.bounds.left + index * 4)
        assert moved.bounds.width == original.bounds.width
        assert tracked.range_bounds(moved.start, moved.end, time=0) == moved.bounds
        if moved.ink_bounds:
            sweep = tracked._sweep_bounds(moved.start, moved.end, moved)
            assert (sweep.left, sweep.right) == (floor(moved.ink_bounds.left) - 3,
                                                 ceil(moved.ink_bounds.right) + 3)


def test_studio_long_reading_centers_on_host_and_reserves_its_overhang():
    doc, index = document(r"{\k50}M|reading{\k50}X")
    layout = layout_document_lyrics(doc, index, studio_spacing=True)
    reading, = layout.ruby
    host = layout.body.range_bounds(0, 1)
    assert reading.layout.bounds.left < host.left
    assert reading.layout.bounds.center == pytest.approx(host.center)
    assert layout.bounds.left == reading.layout.bounds.left


@pytest.mark.parametrize(("reading", "spread"), [("да", True), ("da", False), ("??", False)])
def test_studio_ruby_shares_spare_width_by_script(reading, spread):
    doc, index = document(r"{\k50}ЖЖЖЖ|" + reading)
    layout = layout_document_lyrics(doc, index, studio_spacing=True, min_outline_gap=None)
    ruby, = layout.ruby
    first, second = ruby.layout.characters
    natural = first.bounds.width + second.bounds.width
    spare = layout.body.bounds.width - natural
    assert spare > 0
    assert ruby.layout.bounds.center == pytest.approx(layout.body.bounds.center)
    assert second.bounds.left - first.bounds.right == pytest.approx(spare / 3 if spread else 0)


def test_studio_spacing_uses_selected_em_and_preserves_overhanging_ink():
    from kara_templater import StudioSpacing, Track, prepare_tracks

    doc, _ = document(r"{\k100}j f|j f")
    doc.styles["Default"].italic = True
    def measured(settings):
        scene = prepare_tracks(doc, tracks=(Track(id="main", min_outline_gap=None, studio_spacing=settings),))
        return scene.lines[0].layout

    default = measured(True)
    adjusted = measured(StudioSpacing(allow_biting=True, space_width_percent=50))
    for before, after in ((default.body, adjusted.body),
                          (default.ruby[0].layout, adjusted.ruby[0].layout)):
        j, space, f = after.characters
        assert space.bounds.width == round(space.em_size) // 2
        assert space.bounds.width > before.characters[1].bounds.width
        assert j.bounds.width < before.characters[0].bounds.width
        assert j.ink_bounds and before.characters[0].ink_bounds
        assert j.ink_bounds.width == before.characters[0].ink_bounds.width
        assert f.start == before.characters[2].start
        assert after.singing == before.singing
