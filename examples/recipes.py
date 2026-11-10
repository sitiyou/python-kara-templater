"""Standalone application-style fixtures: python -m examples.recipes /tmp/recipes.ass."""

import argparse
from dataclasses import replace
from pathlib import Path

from kara_templater import (
    Color,
    ColorSpan,
    DisplayWindow,
    Document,
    EdgeSweep,
    Fade,
    Glow,
    HighlightTrack,
    KaraokeEffect,
    KaraokeItem,
    KaraokeLine,
    Paint,
    PaintPair,
    ProgressCurve,
    Pulse,
    Region,
    RubyPaint,
    RubyPolicy,
    Segment,
    SingingPass,
    Style,
    Sweep,
    TextRange,
    TextUnit,
    TrackStyle,
    render_karaoke,
)
from kara_templater.ass import EVENT_FORMAT, STYLE_FORMAT


def build():
    styles = (
        Style(
            name="K1",
            fontname="DejaVu Sans",
            fontsize=40,
            align=1,
            margin_l=40,
            margin_v=90,
        ),
        Style(
            name="K2",
            fontname="DejaVu Sans",
            fontsize=40,
            align=3,
            margin_r=40,
            margin_v=25,
        ),
        Style(name="H1", fontname="DejaVu Sans", fontsize=32, align=8, margin_v=25),
        Style(name="H2", fontname="DejaVu Sans", fontsize=32, align=8, margin_v=110),
        Style(
            name="LEAD",
            fontname="DejaVu Sans",
            fontsize=40,
            align=1,
            margin_l=40,
            margin_v=160,
        ),
    )
    source = Document.parse(
        "[Script Info]\nPlayResX: 640\nPlayResY: 480\nScaledBorderAndShadow: yes\n"
        "[V4+ Styles]\nFormat: "
        + STYLE_FORMAT
        + "\n"
        + "\n".join(s.serialize() for s in styles)
        + "\n[Events]\nFormat: "
        + EVENT_FORMAT
        + "\n"
    )
    window = DisplayWindow(0, 3000)
    lyrics = KaraokeLine(
        (
            TextUnit("Ka", (Segment(1000, 1400, "ka"),)),
            TextUnit("raoke", (Segment(1400, 2000, "raoke"),)),
        )
    )
    items = tuple(
        KaraokeItem(style.name, lyrics, style.name, window) for style in styles[:3]
    )
    items += (
        KaraokeItem(
            "H2",
            KaraokeLine((TextUnit("AB", (Segment(1000, 2000, "ab"),)),)),
            "H2",
            window,
        ),
        KaraokeItem(
            "LEAD",
            KaraokeLine((TextUnit("....", (Segment(500, 1000),)),)),
            "LEAD",
            window,
        ),
    )
    cyan, pink = Color.hex("#33ddff"), Color.hex("#ff5599")
    theme = PaintPair(
        before=Paint(Color(220, 220, 220), border=1),
        after=Paint(cyan, border=1, glow=Glow(cyan, blur=3, border=2, opacity=0.5)),
    )
    primary = KaraokeEffect(
        paints=theme,
        fade=Fade(300, 300),
        pulses=(Pulse.whole_syllable(),),
        sweep=Sweep(
            ProgressCurve.two_stage(time_fraction=0.25, progress_fraction=0.4),
            EdgeSweep(4, 80, 100),
        ),
        ruby=RubyPolicy(offset_y=-4, follow="syllable"),
    )

    def parallel(target, context):
        box = context.layout.units[1].box
        track = HighlightTrack(
            "echo",
            1,
            (SingingPass(1200, 1750, Region(box.left, box.right)),),
            end_behavior="hide",
        )
        from kara_templater import tracks_from_layout

        return replace(
            primary,
            pulses=(),
            sweep=Sweep(edges=EdgeSweep(4, 80, 100)),
            tracks=(*tracks_from_layout(context.layout), track),
            track_styles=(TrackStyle("echo", Paint(pink, border=1), 10),),
            overlap="priority",
        ).build(target, context)

    effects = {
        "K1": primary,
        "K2": parallel,
        "H1": replace(
            primary, pulses=(Pulse.simultaneous_chars(),), ruby=RubyPolicy(offset_y=-4)
        ),
        "H2": KaraokeEffect(
            paints=theme,
            spans=(ColorSpan(TextRange(0, 1, 2), after=Paint(pink)),),
            ruby_paints=(RubyPaint(0, 0, theme),),
            pulses=(Pulse.each_char(),),
        ),
        "LEAD": KaraokeEffect.guide(paints=theme, fade=Fade(200, 300)),
    }
    result = render_karaoke(source, items, effect=effects, owner="example")
    assert (
        render_karaoke(
            result.document, items, effect=effects, owner="example"
        ).document.dumps()
        == result.document.dumps()
    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = build()
    result.document.save(args.output)
    print(
        f"{result.event_count} events, {result.layer_count} planned layers, {len(result.diagnostics)} diagnostics"
    )
    for diagnostic in dict.fromkeys(result.diagnostics):
        print(diagnostic)


if __name__ == "__main__":
    main()
