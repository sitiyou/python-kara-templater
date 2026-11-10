import pytest

from kara_templater import KaraokeLine, Segment, Style, TextUnit, layout_line
from kara_templater.appearance import (
    ColorSpan,
    PaintPair,
    RubyPaint,
    resolve_paints,
    resolve_ruby_paints,
)
from kara_templater.characters import TextRange, layout_characters
from kara_templater.composition import Color, Paint
from kara_templater.timeline import tracks_from_layout

RED = Paint(Color(255, 0, 0))
BLUE = Paint(Color(0, 0, 255))
STYLE = Style(fontname="DejaVu Sans", fontsize=40)


def setup_line():
    layout = layout_line(
        KaraokeLine((TextUnit("AB", (Segment(1000, 2000, "reading"),)),)), style=STYLE
    )
    return layout, layout_characters(layout, style=STYLE)


def test_colors_do_not_split_or_retime_singing():
    layout, chars = setup_line()
    tracks = tracks_from_layout(layout)
    paints = resolve_paints(
        chars,
        spans=(
            ColorSpan(TextRange(0, 0, 1), after=RED),
            ColorSpan(TextRange(0, 1, 2), after=BLUE),
        ),
    )
    assert [p.paints.after for p in paints] == [RED, BLUE]
    assert tracks_from_layout(layout) == tracks
    assert len(tracks[0].passes) == 1
    assert paints[0].highlighted(BLUE) == BLUE
    assert paints[0].highlighted() == RED


def test_priority_conflict_and_independent_before_after_states():
    _, chars = setup_line()
    source = TextRange(0, 0, 2)
    spans = (ColorSpan(source, after=RED), ColorSpan(source, before=BLUE))
    assert all(
        p.paints == PaintPair(BLUE, RED) for p in resolve_paints(chars, spans=spans)
    )
    with pytest.raises(ValueError, match="conflicting after"):
        resolve_paints(chars, spans=(*spans, ColorSpan(source, after=BLUE)))
    assert all(
        p.paints.after == BLUE
        for p in resolve_paints(
            chars, spans=(*spans, ColorSpan(source, after=BLUE, priority=1))
        )
    )


def test_ruby_inheritance_requires_explicit_mapping_for_mixed_colors():
    layout, chars = setup_line()
    plain = resolve_paints(chars, default=PaintPair(after=RED))
    assert resolve_ruby_paints(layout, plain)[0].paints.after == RED
    mixed = resolve_paints(chars, spans=(ColorSpan(TextRange(0, 0, 1), after=BLUE),))
    with pytest.raises(ValueError, match="ambiguous body colors"):
        resolve_ruby_paints(layout, mixed)
    explicit = RubyPaint(0, 0, PaintPair(after=RED))
    assert resolve_ruby_paints(layout, mixed, overrides=(explicit,)) == (explicit,)
    with pytest.raises(ValueError, match="missing readings"):
        resolve_ruby_paints(layout, plain, overrides=(RubyPaint(0, 3, PaintPair()),))
