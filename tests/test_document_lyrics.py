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


@pytest.mark.parametrize("rtl", [False, True])
def test_reading_outline_spacing_is_independent_of_timing_checkpoints(rtl):
    def measured(text):
        doc, index = document(text)
        layout = layout_document_lyrics(
            doc, index, studio_spacing=True, min_outline_gap=2, reserved_border=6,
            right_to_left=rtl,
        )
        return [c for r in layout.ruby for c in r.layout.characters]

    whole = measured(r"{\k40}A|HH")
    split = measured(r"{\k20}A|H{\k20}#|H")
    assert [c.bounds for c in split] == [c.bounds for c in whole]
    left, right = sorted(split, key=lambda c: c.bounds.left)
    assert left.ink_bounds and right.ink_bounds
    assert right.ink_bounds.left - left.ink_bounds.right >= 14 - 1e-8


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


@pytest.mark.parametrize(("marker", "kind"), [("", "join"), ("!", "break"), ("！", "break"),
                                              ("<", "spill"), ("＜", "spill")])
def test_adjacent_wide_ruby_groups_and_continuation_clocks(marker, kind):
    doc, index = document(r"{\k10}M｜a{\k10}N｜" + marker + r"long{\k10}＃｜word")
    scene = layout_document_lyrics(doc, index, min_outline_gap=None)
    first, second = (c.bounds for c in scene.body.characters)
    r1, r2, r3 = (r.layout.bounds for r in scene.ruby)
    assert r3.left == pytest.approx(r2.right)
    if kind == "join":
        assert r1.left == pytest.approx(first.left)
        assert r2.left == pytest.approx(r1.right)
    else:
        assert r1.center == pytest.approx(first.center)
        if kind == "spill":
            assert (r2.left + r3.right) / 2 == pytest.approx(second.center)
            assert r2.left == pytest.approx(first.right, abs=0.25)
        else:
            assert r2.left == pytest.approx(second.left)
    assert [r.segment_index for r in scene.ruby] == [0, 0, 1]
    assert [s.singing.end - s.singing.start for s in scene.lyrics.units[-1].segments] == pytest.approx([0.1, 0.1])


def test_short_readings_across_two_syllables_center_as_one_run():
    doc, index = document(r"{\k10}MMM|a{\k20}MMM|b")
    layout = layout_document_lyrics(doc, index, min_outline_gap=None)
    first, second = (r.layout.bounds for r in layout.ruby)
    assert first.right == pytest.approx(second.left)
    assert (first.left + second.right) / 2 == pytest.approx(layout.body.bounds.center)


def test_spill_on_a_continuation_applies_to_its_whole_group():
    doc, index = document(r"{\k10}X|a{\k10}#|＜long")
    layout = layout_document_lyrics(doc, index)
    first, last = layout.ruby
    assert (first.layout.bounds.left + last.layout.bounds.right) / 2 == pytest.approx(layout.body.bounds.center)


@pytest.mark.parametrize("bare", ["", "X", "XXXX", "XXXXXXXX"])
def test_bare_syllable_consumes_previous_overflow_before_next_short_reading(bare):
    first = r"{\k10}M|verylongreading"
    middle = r"{\k10}" + bare if bare else ""
    doc, index = document(first + middle + r"{\k10}MMMM|!a")
    layout = layout_document_lyrics(doc, index, min_outline_gap=None)
    wide, short = layout.ruby
    host = layout.body.range_bounds(1 + len(bare), 5 + len(bare))
    baseline = layout.body.range_bounds(0, 1 + len(bare))
    assert host.left == pytest.approx(max(wide.layout.bounds.right, baseline.right), abs=0.5)
    assert short.layout.bounds.center == pytest.approx(host.center)


def test_spaces_surrounding_an_annotated_syllable_belong_to_its_body():
    doc, index = document(r"{\k10} A|a  {\k10} ＃｜b ")
    lyrics = parse_document_lyrics(doc.text_at(index), start=1)
    assert lyrics.body.text == " A  "
    assert [s.ruby.source.text for s in lyrics.units[0].segments if s.ruby] == ["a", "b"]


def test_float_left_long_reading_centers_on_host_and_reserves_its_overhang():
    doc, index = document(r"{\k50}M|<reading{\k50}X")
    layout = layout_document_lyrics(doc, index, studio_spacing=True)
    reading, = layout.ruby
    host = layout.body.range_bounds(0, 1)
    assert reading.layout.bounds.left < host.left
    assert reading.layout.bounds.center == pytest.approx(host.center)
    assert layout.bounds.left == reading.layout.bounds.left


@pytest.mark.parametrize("reading", ["だよ", "да", "da", "??"])
def test_short_reading_centers_at_its_natural_spacing(reading):
    doc, index = document(r"{\k50}ЖЖЖЖ|" + reading)
    layout = layout_document_lyrics(doc, index, studio_spacing=True, min_outline_gap=None)
    ruby, = layout.ruby
    first, second = ruby.layout.characters
    natural = first.bounds.width + second.bounds.width
    spare = layout.body.bounds.width - natural
    assert spare > 0
    assert ruby.layout.bounds.center == pytest.approx(layout.body.bounds.center)
    assert second.bounds.left - first.bounds.right == pytest.approx(0)


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


def test_timed_vector_guide_preserves_ruby_and_singing_in_ass_exports(tmp_path):
    from kara_templater import (
        KaraokeEffects,
        Track,
        Vec2,
        VectorGuide,
        VectorPath,
        prepare_tracks,
    )
    from kara_templater._raster import rasterize

    doc, index = document(r"{\k50}◆|!x{\k50}A")
    guide = VectorGuide(VectorPath.rectangle(0.6, 0.4).map(lambda p: p + Vec2(0.1, -0.7)), 0.8)
    recipe = KaraokeEffects(entry="none", singing="none", exit="none", sung=Color(255, 0, 0))
    scene = prepare_tracks(doc, tracks=(Track(id="lyrics", guide_symbols={"◆": guide}, effects=(recipe,)),))
    layout = scene.lines[0].layout
    glyph = layout.body.characters[0]
    assert glyph.bounds.width == round(0.8 * glyph.object.font_size)
    assert glyph.ink_bounds is not None
    assert glyph.ink_bounds.width == pytest.approx(0.6 * glyph.object.font_size)
    assert layout.ruby[0].body_start == 0
    assert layout.body.singing == tuple(s.singing for u in doc.lyrics_at(index).units for s in u.segments)
    output = scene.ass.compile().document
    rows = [row for row in output.lines if not row.comment]
    assert all("◆" not in row.text for row in rows)
    assert any(r"\p1" in row.text for row in rows)
    counts = []
    for time in (1010, 1250, 1490):
        frame = rasterize(output.dumps(), time, (640, 360)).rgba
        counts.append(sum(r > 180 and g < 80 and a > 180
                          for r, g, a in zip(frame[0::4], frame[1::4], frame[3::4], strict=True)))
    assert counts[0] < counts[1] < counts[2]


def test_anchored_guides_stay_unsung_on_the_shared_onset():
    from kara_templater import (
        KaraokeEffects,
        Track,
        VectorGuide,
        VectorPath,
        prepare_tracks,
    )
    from kara_templater._raster import rasterize

    doc, _ = document(r"{\k0}◆{\k0}◆{\k100}A")
    scene = prepare_tracks(doc, tracks=(Track(
        id="lyrics", guide_symbols={"◆": VectorGuide(VectorPath.rectangle(0.7, 0.3))},
        effects=(KaraokeEffects(entry="none", exit="none", singing="none", sung=Color(255, 0, 0)),),
    ),))
    script = scene.ass.compile(native_tweens=True).document.dumps()
    def has_red(ms):
        frame = rasterize(script, ms, (640, 360)).rgba
        return any(r > 180 and g < 80 and a > 180
                   for r, g, a in zip(frame[0::4], frame[1::4], frame[3::4], strict=True))
    assert has_red(1010)
    assert not has_red(1000)


def test_vertical_reading_continuation_shares_its_host_and_retains_timing():
    from kara_templater._vertical_lyrics import _vertical_line

    doc, index = document(r"{\k25}空|そ{\k25}#|ら{\k50}ー{\k50}ゃ{\k50}。")
    source = layout_document_lyrics(doc, index)
    vertical = _vertical_line(source, cell_width=40, cell_height=49, ruby_width=20, ruby_gap=4)
    body = vertical.body.characters
    assert [g.bounds.top for g in body] == [0, 49, 98, 147]
    assert [g.object.state.rotation for g in body] == [0, 90, 0, 0]
    readings = [r.layout.characters[0] for r in vertical.ruby]
    assert [(g.bounds.center, g.bounds.top) for g in readings] == [(34, 0), (34, 24)]
    assert [r.layout.singing for r in vertical.ruby] == [r.layout.singing for r in source.ruby]
    assert vertical.body.singing == source.body.singing


def test_vertical_track_catalog_wipes_down_across_two_cells_and_rotated_text():
    from kara_templater import KaraokeEffects, Track, prepare_tracks
    from kara_templater._raster import rasterize

    doc, _ = document(r"{\k100}A(B{\k50}C")
    recipe = KaraokeEffects(entry="none", exit="none", singing="utopia_scanline",
                           unsung=Color(255, 255, 255), sung=Color(255, 0, 0))
    scene = prepare_tracks(doc, tracks=(Track(id="main", vertical=True, effects=(recipe,)),))
    assert scene.plans[0].line.layout.body.characters[1].object.state.rotation == 90
    ass = scene.ass.compile(native_tweens=True).document.dumps()
    def last_red_row(ms):
        raster = rasterize(ass, ms, (doc.meta.res_x, doc.meta.res_y))
        return max((i // (4 * doc.meta.res_x) for i in range(0, len(raster.rgba), 4)
                    if raster.rgba[i] > 200 and raster.rgba[i+1] < 64 and raster.rgba[i+3] > 128),
                   default=-1)
    assert -1 == last_red_row(900) < last_red_row(1400) < last_red_row(1900)


def test_vertical_catalog_uses_line_transitions_and_omits_horizontal_ornaments():
    from kara_templater import KaraokeEffects, Track, prepare_tracks

    doc, _ = document(r"{\k50}A|a{\k50}B")
    def plan(recipe):
        return prepare_tracks(doc, tracks=(Track(id="main", vertical=True, effects=(recipe,)),)).plans[0]
    plain = KaraokeEffects(entry="none", exit="none", singing="none")
    baseline = plan(plain)
    ornamental = plan(replace(plain, entry="assemble_in", exit="petal",
                              singing="zoom_pulse_scanline", decoration="snow", stroke_flash=True))
    assert ornamental.line == baseline.line
    assert ornamental.placement == baseline.placement
    assert plan(replace(plain, entry="slide_in", exit="rise")).line.animations


def test_native_vertical_wipe_rounds_the_front_at_the_half_pixel_crossing():
    from kara_templater import (
        KaraokeEffects,
        Track,
        Vec2,
        VectorGuide,
        VectorPath,
        prepare_tracks,
    )
    from kara_templater._raster import rasterize

    doc, _ = document(r"{\k100}X")
    path = VectorPath.polygon(Vec2(0, -1), Vec2(.5, -1), Vec2(.5, 0), Vec2(0, 0))
    track = Track(id="main", vertical=True, guide_symbols={"X": VectorGuide(path)},
                  effects=(KaraokeEffects(entry="none", exit="none", singing="none",
                                          sung=Color(255, 0, 0), unsung=Color(255, 255, 255)),))
    scene = prepare_tracks(doc, tracks=(track,))
    plan = scene.plans[0]
    glyph = plan.line.layout.body.characters[0]
    cell = glyph.bounds
    x = round(plan.placement.position.x + cell.center)
    ass = scene.ass.compile(native_tweens=True).document.dumps()
    for ms in range(1400, 1451, 10):
        front = round(plan.placement.position.y + cell.top + (ms - 1000) * cell.height / 1000)
        frame = rasterize(ass, ms, (doc.meta.res_x, doc.meta.res_y))
        for y, expected in ((front - 1, (255, 0, 0)), (front, (255, 255, 255))):
            offset = (doc.meta.res_x * y + x) * 4
            assert tuple(frame.rgba[offset:offset + 3]) == expected
