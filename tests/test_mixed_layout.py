from dataclasses import replace

import pytest

from kara_templater import (
    DisplayWindow,
    EffectContext,
    HighlightTrack,
    KaraokeEffect,
    KaraokeItem,
    KaraokeLine,
    Pulse,
    Region,
    Segment,
    SingingPass,
    Style,
    TextUnit,
    compile_layers,
    layout_characters,
    layout_line,
    text_extents,
    tracks_from_layout,
)


def fixture():
    source = KaraokeLine(
        (
            TextUnit("["),
            TextUnit("", (Segment(0, 100),)),
            TextUnit("\u00a0", (Segment(100, 200),)),
            TextUnit(
                "AB",
                (
                    Segment(200, 300),
                    Segment(300, 500, "i"),
                    Segment(500, 600),
                    Segment(600, 900, "WWW"),
                ),
            ),
            TextUnit("]"),
        )
    )
    style = Style(fontname="DejaVu Sans", fontsize=40)
    ruby_style = replace(style, name="ruby", fontsize=20)
    layout = layout_line(
        source, style=style, ruby_style=ruby_style, resolution=(640, 480)
    )
    return source, EffectContext(layout, style, ruby_style, (640, 480))


def test_mixed_static_empty_and_multiple_readings_keep_source_time():
    source, context = fixture()
    layout = context.layout
    assert tuple(u.source for u in layout.units) == source.units
    assert layout.units[1].box.width == 0
    assert layout.units[2].box.width > 0
    unit = layout.units[3]
    first_empty, first, middle_empty, last = unit.segments
    assert first_empty.left == first_empty.right == unit.box.left
    assert middle_empty.left == middle_empty.right == first.right == last.left
    assert first_empty.ruby is None and middle_empty.ruby is None
    ratio = (
        text_extents(context.ruby_style, "i")[0]
        / text_extents(context.ruby_style, "WWW")[0]
    )
    assert (first.right - first.left) / (last.right - last.left) == pytest.approx(ratio)
    tracks = tracks_from_layout(layout)
    assert [t.unit_index for t in tracks] == [1, 2, 3]
    assert tracks[0].regions_at(1000) == ()
    sung = tracks[-1]
    assert [(p.start_ms, p.end_ms) for p in sung.passes] == [
        (s.start_ms, s.end_ms) for s in source.units[3].segments
    ]
    assert sung.regions_at(299) == ()
    assert (
        sung.regions_at(500)
        == sung.regions_at(599)
        == (Region(first.left, first.right),)
    )
    assert sung.regions_at(900) == (Region(unit.box.left, unit.box.right),)
    plan = KaraokeEffect(pulses=(Pulse.each_char(),)).build(
        KaraokeItem("mixed", source, "Default", DisplayWindow(0, 1000)), context
    )
    animations = {a for layer in plan.layers for a in layer.animations}
    assert len(animations) == 2
    assert all(
        a.target_id.startswith("unit:3/") and a.start_ms >= 300 for a in animations
    )
    static = [layer for layer in plan.layers if layer.text in "[]"]
    assert static and all(not layer.animations for layer in static)
    assert compile_layers(plan.layers).events


def test_explicit_body_regions_replace_reading_weights_without_changing_source():
    source, context = fixture()
    chars = [
        c
        for c in layout_characters(context.layout, style=context.style)
        if c.source.unit_index == 3
    ]
    track = HighlightTrack(
        "manual",
        3,
        (
            SingingPass(200, 400, chars[0].timing_region),
            SingingPass(600, 800, chars[1].timing_region),
        ),
    )
    plan = KaraokeEffect(tracks=(track,), pulses=(Pulse.each_char(),)).build(
        KaraokeItem("mapped", source, "Default", DisplayWindow(0, 1000)), context
    )
    animations = {a for layer in plan.layers for a in layer.animations}
    assert {(a.start_ms, a.end_ms) for a in animations} == {(200, 400), (600, 800)}
    assert context.layout.units[3].source.segments == source.units[3].segments
    assert (
        len(
            {layer.animation_id for layer in plan.layers if "/ruby:" in layer.source_id}
        )
        == 2
    )
