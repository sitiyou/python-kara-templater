import os
import subprocess
import sys
from dataclasses import replace
from itertools import pairwise
from pathlib import Path
from xml.sax.saxutils import escape

import pytest

from kara_templater import KaraokeLine, Segment, Style, TextUnit, layout_line
from kara_templater.characters import (
    LayoutCapabilityError,
    TextRange,
    layout_characters,
    select_characters,
)

STYLE = Style(fontname="DejaVu Sans", fontsize=40)


def test_karaoke_guide_dots_have_verified_ink_and_separate_timing_regions():
    layout, chars = measured("●●●")
    assert [c.text for c in chars] == ["●", "●", "●"]
    assert all(c.ink_bounds is not None and c.target.drawable for c in chars)
    assert chars[0].timing_region.left == layout.box.left
    assert chars[-1].timing_region.right == layout.box.right
    assert all(
        a.timing_region.right == b.timing_region.left for a, b in pairwise(chars)
    )


def test_japanese_prolonged_sound_mark_keeps_its_source_offset():
    from kara_templater.characters import _clusters

    assert _clusters("コーラス") == [
        (0, 1, "コ"),
        (1, 2, "ー"),
        (2, 3, "ラ"),
        (3, 4, "ス"),
    ]


def test_japanese_iteration_mark_keeps_source_and_verified_ink():
    from kara_templater import load_font

    font = load_font(Path(__file__).parent / "fonts/KaraTestCJK.ttf")
    layout, chars = measured("時々", replace(STYLE, fontname=font.family))
    assert [c.text for c in chars] == ["時", "々"]
    assert [c.source for c in chars] == [TextRange(0, 0, 1), TextRange(0, 1, 2)]
    assert all(c.ink_bounds is not None and c.target.drawable for c in chars)
    assert chars[1].timing_region.right == layout.box.right
    assert select_characters(chars, TextRange(0, 1, 2)) == (chars[1],)


@pytest.mark.parametrize(
    "composed,decomposed,ranges",
    [
        ("한글", "한글", ((0, 3), (3, 6))),
        ("가각", "가각", ((0, 2), (2, 5))),
    ],
)
def test_modern_hangul_jamo_preserve_syllable_clusters_and_source_offsets(
    composed, decomposed, ranges
):
    from kara_templater import load_font

    font = load_font(Path(__file__).parent / "fonts/KaraTestHangul.ttf")
    style = replace(STYLE, fontname=font.family)
    reference_layout, reference = measured(composed, style)
    layout, chars = measured(decomposed, style)
    assert tuple((c.source.start, c.source.end) for c in chars) == ranges
    assert "".join(c.text for c in chars) == decomposed
    assert layout.box == reference_layout.box
    assert [(c.box, c.ink_bounds, c.timing_region, c.font_faces) for c in chars] == [
        (c.box, c.ink_bounds, c.timing_region, c.font_faces) for c in reference
    ]
    with pytest.raises(LayoutCapabilityError, match="cuts a drawable cluster"):
        select_characters(chars, TextRange(0, 0, 1))

    assert arrival_times(decomposed, style) == arrival_times(composed, style)


@pytest.mark.skipif(
    sys.platform != "linux",
    reason="isolated Fontconfig test requires the Linux font provider",
)
def test_missing_glyph_is_rejected_in_controlled_font_environment(tmp_path):
    fonts = Path(__file__).parent / "fonts"
    config = tmp_path / "fonts.conf"
    config.write_text(
        '<?xml version="1.0"?><fontconfig><dir>'
        + escape(str(fonts.resolve()))
        + "</dir><cachedir>"
        + escape(str(tmp_path / "cache"))
        + "</cachedir></fontconfig>"
    )
    code = """
from kara_templater import FontFace, KaraokeLine, TextUnit, Style, layout_line, layout_characters
from kara_templater.characters import LayoutCapabilityError
style = Style(fontname="DejaVu Sans", fontsize=40)
for text in ("A", "a\\u0301", " "):
    layout = layout_line(KaraokeLine((TextUnit(text),)), style=style)
    assert layout_characters(layout, style=style)
layout = layout_line(KaraokeLine((TextUnit("\\U00031350"),)), style=style)
try:
    layout_characters(layout, style=style)
except LayoutCapabilityError as error:
    assert "U+31350" in str(error) and "missing glyph" in str(error), error
    assert error.source_indices == ((0, None),)
    assert isinstance(error.__cause__, ValueError)
else:
    raise AssertionError("missing-glyph outline was accepted as a drawable character")
fallback_style = Style(fontname="KaraTestNonexistentFamily", fontsize=40)
layout = layout_line(KaraokeLine((TextUnit("A"),)), style=fallback_style)
characters = layout_characters(layout, style=fallback_style)
assert characters[0].font_faces == (FontFace("DejaVu Sans", "Book"),), characters[0].font_faces
mixed_style = Style(fontname="Kara Test Primary", fontsize=40)
layout = layout_line(KaraokeLine((TextUnit("AB"),)), style=mixed_style)
characters = layout_characters(layout, style=mixed_style)
assert [c.text for c in characters] == ["A", "B"]
assert characters[0].font_faces == (FontFace("Kara Test Primary", "Regular"),)
assert characters[1].font_faces == (FontFace("DejaVu Sans", "Book"),)
assert characters[0].source.start == 0 and characters[1].source.start == 1
from kara_templater import Document, Line, layout_document_text
document = Document.create(styles=(mixed_style,))
document.records.append(Line(text="AB", start_time=1000, end_time=2000))
record_index = len(document.records) - 1
bound = layout_document_text(document, record_index)
assert [item.fonts for item in bound.characters] == [c.font_faces for c in characters]
assert [(item.start, item.end) for item in bound.characters] == [(0, 1), (1, 2)]
document.records[record_index] = Line(text="\\U00031350", start_time=1000, end_time=2000)
try:
    layout_document_text(document, record_index)
except LayoutCapabilityError as error:
    assert f"record {record_index}, decoded text range 0:1" in str(error), error
    assert "missing glyph" in str(error), error
    assert isinstance(error.__cause__, LayoutCapabilityError)
else:
    raise AssertionError("Document binding accepted a missing glyph")
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
        env={
            **os.environ,
            "FONTCONFIG_FILE": str(config),
            "FONTCONFIG_PATH": str(tmp_path),
        },
    )
    assert result.returncode == 0, result.stdout + result.stderr


def measured(text, style=STYLE):
    layout = layout_line(
        KaraokeLine((TextUnit(text, (Segment(1000, 2000),)),)), style=style
    )
    return layout, layout_characters(layout, style=style)


def test_actual_font_faces_cover_clusters_and_survive_renderer_reuse():
    from kara_templater import FontFace

    _, chars = measured("office a\u0301 ")
    faces = tuple(c.font_faces for c in chars)
    assert any(c.text == "ffi" for c in chars)
    for char in chars:
        assert char.font_faces == (FontFace("DejaVu Sans", "Book"),)
        if char.text.isspace():
            assert char.ink_bounds is None
    measured("other text")
    assert tuple(c.font_faces for c in chars) == faces


def test_combining_mark_source_mapping_and_space_advance():
    layout, chars = measured("a\u0301 b")
    assert [c.text for c in chars] == ["a\u0301", " ", "b"]
    assert [c.source for c in chars] == [
        TextRange(0, 0, 2),
        TextRange(0, 2, 3),
        TextRange(0, 3, 4),
    ]
    assert chars[1].box.width > 0 and not chars[1].target.drawable
    assert chars[0].ink_bounds is not None
    assert chars[0].box.left == pytest.approx(layout.units[0].box.left, abs=1 / 64)
    assert chars[-1].box.right == pytest.approx(layout.units[0].box.right, abs=0.2)
    assert select_characters(chars, TextRange(0, 0, 2)) == (chars[0],)
    with pytest.raises(LayoutCapabilityError, match="cuts a drawable cluster"):
        select_characters(chars, TextRange(0, 0, 1))


@pytest.mark.parametrize(
    "space", ["\u00a0", "\u2002", "\u2003", "\u2009", "\u202f", "\u3000"]
)
def test_unicode_spacing_retains_advance_without_a_pulse_target(space):
    layout, chars = measured("A" + space + "B")
    assert [c.source for c in chars] == [TextRange(0, i, i + 1) for i in range(3)]
    assert chars[1].text == space
    assert chars[1].box.width > 0 and not chars[1].target.drawable
    assert chars[1].ink_bounds is None
    assert chars[0].timing_region.right == chars[1].timing_region.left
    assert chars[1].timing_region.right == chars[2].timing_region.left
    assert chars[-1].timing_region.right == layout.box.right


def test_printed_lyric_star_has_its_own_visible_source_range():
    _, chars = measured("ABC☆")
    assert chars[-1].text == "☆"
    assert chars[-1].source == TextRange(0, 3, 4)
    assert chars[-1].target.drawable


def test_ligature_is_preserved_as_one_verified_drawable_cluster():
    _, chars = measured("office")
    assert [c.text for c in chars] == ["o", "ffi", "c", "e"]
    assert chars[1].source == TextRange(0, 1, 4)
    assert select_characters(chars, TextRange(0, 1, 4)) == (chars[1],)
    with pytest.raises(LayoutCapabilityError, match="cuts a drawable cluster"):
        select_characters(chars, TextRange(0, 1, 2))


def test_ligatures_do_not_absorb_spaces_or_following_words():
    _, chars = measured("ffi fi")
    assert [c.text for c in chars] == ["ffi", " ", "fi"]
    assert not chars[1].target.drawable


@pytest.mark.parametrize("text", ["Karaoke", "office ffi"])
def test_positioned_cluster_outlines_match_original_subpixel_phase(text):
    from kara_templater.characters import _shape

    style = replace(STYLE, fontsize=52)
    layout, chars = measured(text, style)
    original = _shape(style, text, layout.box.left)[4]
    cursor = 0
    for char in chars:
        isolated = _shape(style, char.text, char.box.left)[4]
        actual = original[cursor : cursor + len(isolated)]
        for (points, segments, _, face), (
            reference,
            reference_segments,
            _,
            reference_face,
        ) in zip(actual, isolated, strict=True):
            assert segments == reference_segments
            assert face == reference_face
            for (x, y), (rx, ry) in zip(points, reference, strict=True):
                assert x + layout.box.left == pytest.approx(
                    rx + char.box.left, abs=1 / 64
                )
                assert y + layout.box.top == pytest.approx(
                    ry + char.box.top, abs=1 / 64
                )
        cursor += len(isolated)
    assert cursor == len(original)


def test_multimark_clusters_keep_source_ranges_at_fractional_placement():
    _, chars = measured("x\u0301 a\u0323\u0301", replace(STYLE, fontsize=52))
    assert [char.text for char in chars] == ["x\u0301", " ", "a\u0323\u0301"]


def test_pinned_oblique_keeps_ink_overhang_separate_from_timing():
    from kara_templater import load_font

    font = load_font(Path(__file__).parent / "fonts/DejaVuSans-Oblique.ttf")
    assert (
        font.sha256
        == "cf41fd01245e40e783ce3eae0bba5c38927a2497889dde1266d8757b9c84de1a"
    )
    layout, chars = measured("AV fj", replace(STYLE, italic=True, fontsize=52))
    assert any(
        c.ink_bounds is not None
        and (c.ink_bounds.left < c.box.left or c.ink_bounds.right > c.box.right)
        for c in chars
    )
    assert chars[0].timing_region.left == layout.box.left
    assert chars[-1].timing_region.right == layout.box.right


@pytest.mark.parametrize(
    "text", ["سلام", "क", "👩‍💻", "🇨🇳", "ᄓᅡ", "a\nb", "a\u200db", "\u0301"]
)
def test_unsupported_shaping_has_source_diagnostic(text):
    with pytest.raises(
        LayoutCapabilityError, match="unit 0: unsupported cluster at source offset"
    ):
        measured(text)


def test_cjk_kana_and_precomposed_hangul_can_be_drawn_independently():
    from kara_templater import load_font

    font = load_font(Path(__file__).parent / "fonts/KaraTestMultiscript.ttf")
    for text in ("今天", "かな", "한글"):
        _, chars = measured(text, replace(STYLE, fontname=font.family))
        assert len(chars) == 2
        assert all(c.target.drawable for c in chars)


def test_font_style_mismatch_rejected():
    layout, _ = measured("AB")
    with pytest.raises(LayoutCapabilityError, match="does not match"):
        layout_characters(layout, style=replace(STYLE, fontsize=20))


def test_native_shapes_survive_subsequent_measurements():
    from kara_templater.characters import _shape

    first = _shape(STYLE, "A")
    expected = repr(first)
    from kara_templater import load_font

    font = load_font(Path(__file__).parent / "fonts/KaraTestMultiscript.ttf")
    _shape(replace(STYLE, fontname=font.family), "今天")
    assert repr(first) == expected


def test_spacing_and_scale_preserve_measured_positions():
    style = replace(STYLE, spacing=5, scale_x=125, scale_y=80)
    layout, chars = measured("ABC", style)
    assert len(chars) == 3
    assert chars[-1].box.right == pytest.approx(layout.box.right, abs=0.2)


def test_measured_characters_feed_common_arrival_without_edge_rounding_loss():
    times = arrival_times("AV", STYLE)
    assert len(times) == 2
    assert times[-1].end == 2
    assert times[0].end == times[1].start
    assert 1 < times[1].start < 2


def arrival_times(text: str, style: Style):
    from kara_templater import (
        RED,
        Document,
        Highlight,
        HighlightArrival,
        HighlightPass,
        Lifetime,
        Line,
        LyricLine,
        Region,
        StatePatch,
        TimeSpan,
        layout_document_lyrics,
    )

    source = Document.create(styles=(style,))
    source.records.append(Line(start_time=1000, end_time=2000, text=r"{\k100}" + text))
    line = LyricLine.from_layout(
        layout_document_lyrics(
            source,
            len(source.records) - 1,
            display=Lifetime(0.5, 2.5),
        )
    )
    box = line.layout.body.bounds
    anchor = HighlightArrival(
        highlights=(
            Highlight(
                "sung",
                0,
                (HighlightPass(TimeSpan(1, 2), Region(box.left, box.right)),),
                StatePatch(fill=RED),
            ),
        )
    )
    return tuple(anchor(line, target)[0] for target in line.query("character"))
