from kara_templater import (
    Box,
    LaidOutSegment,
    LaidOutUnit,
    Segment,
    SweepSettings,
    TextUnit,
    render_sweep,
)


def test_sweep_preserves_independent_intervals_and_ruby():
    segments = (Segment(1000, 1500, "a"), Segment(2000, 2500, "b"))
    unit = LaidOutUnit(
        TextUnit("字", segments),
        Box(100, 100, 80, 80),
        tuple(
            LaidOutSegment(s, 100 + i * 40, 140 + i * 40, Box(100 + i * 40, 60, 40, 40)) for i, s in enumerate(segments)
        ),
    )
    palettes = (
        ("0000FF", "0000AA", "222222", "333333", "EEEEEE"),
        ("00FF00", "00AA00", "222222", "333333", "EEEEEE"),
    )
    events = render_sweep(unit, "K1", 500, 3000, SweepSettings(), palettes[0], segment_colours=palettes)
    assert len(events) == 14
    assert all(e.start_time == 500 and e.end_time == 3000 for e in events)
    base = [e for e in events if e.style == "K1" and e.layer == 3]
    assert len(base) == 2
    assert r"\1c&H0000FF&" in base[0].text
    assert r"\1c&H00FF00&" in base[1].text
    assert r"\t(500," in base[0].text
    assert r"\t(1500," in base[1].text
    ruby = [e for e in events if e.style == "K1-furigana" and e.layer == 3]
    assert len(ruby) == 2
    assert ruby[0].text.endswith("a")
    assert ruby[1].text.endswith("b")


def test_sweep_ignores_hidden_or_blank_units():
    unit = LaidOutUnit(TextUnit(" "), Box(0, 0, 10, 10), ())
    palette = ("0000FF", "0000AA", "222222", "333333", "EEEEEE")
    assert render_sweep(unit, "K1", 0, 1000, SweepSettings(), palette) == []
    unit = LaidOutUnit(TextUnit("a"), unit.box, ())
    assert render_sweep(unit, "K1", 1000, 1000, SweepSettings(), palette) == []
