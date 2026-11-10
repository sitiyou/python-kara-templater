"""Compare three simultaneous sweep policies on one multi-character segment.

Run: python -m examples.parallel_tracks /tmp/parallel.ass
Rows, top to bottom: disjoint regions, priority override, translucent layers.
All rows preserve the same source timing and character layout.
"""

import argparse
from pathlib import Path

from kara_templater import (
    Color,
    ColorSpan,
    DisplayWindow,
    Document,
    HighlightTrack,
    KaraokeEffect,
    KaraokeItem,
    KaraokeLine,
    Paint,
    PaintPair,
    Region,
    RubyPolicy,
    Segment,
    SingingPass,
    Style,
    TextRange,
    TextUnit,
    TrackStyle,
    render_karaoke,
)
from kara_templater.ass import EVENT_FORMAT, STYLE_FORMAT


def build():
    styles = tuple(
        Style(name=name, fontname="DejaVu Sans", fontsize=52, align=8,
              margin_v=margin)
        for name, margin in (("regions", 60), ("priority", 200), ("layer", 340))
    )
    document = Document.parse(
        "[Script Info]\nPlayResX: 640\nPlayResY: 480\n"
        "ScaledBorderAndShadow: yes\n[V4+ Styles]\nFormat: "
        + STYLE_FORMAT + "\n"
        + "\n".join(style.serialize() for style in styles)
        + "\n[Events]\nFormat: " + EVENT_FORMAT + "\n"
    )
    # Colour boundaries and sweep tracks do not split this singing segment.
    source = KaraokeLine((TextUnit("Karaoke", (Segment(1000, 2400),)),))
    items = tuple(
        KaraokeItem(style.name, source, style.name, DisplayWindow(0, 3000))
        for style in styles
    )
    cyan = Paint(Color.hex("#33ddff"))
    pink = Paint(Color.hex("#ff5599"))

    def effect(target, context):
        box = context.layout.units[0].box
        whole = Region(box.left, box.right)
        if target.id == "regions":
            # Both halves begin simultaneously, at independent positions.
            center = whole.center
            tracks = (
                HighlightTrack("left", 0, (
                    SingingPass(1000, 2400, Region(whole.left, center)),
                )),
                HighlightTrack("right", 0, (
                    SingingPass(1000, 2400, Region(center, whole.right)),
                )),
            )
            track_styles = ()
            overlap = "union"
        else:
            tracks = (
                HighlightTrack("main", 0, (SingingPass(1000, 2400, whole),)),
                HighlightTrack("echo", 0, (SingingPass(1200, 2000, whole),),
                               end_behavior="hide"),
            )
            # Explicit priorities determine both override and stacking order.
            # The echo disappears at 2000 ms, revealing the main sweep.
            opacity = 0.5 if target.id == "layer" else 1
            track_styles = (
                TrackStyle("main", Paint(cyan.fill, opacity=opacity), 0),
                TrackStyle("echo", Paint(pink.fill, opacity=opacity), 10),
            )
            overlap = target.id
        return KaraokeEffect(
            paints=PaintPair(before=Paint(Color(160, 160, 160)), after=cyan),
            spans=(ColorSpan(TextRange(0, 4, 7), after=pink),),
            tracks=tracks, track_styles=track_styles, overlap=overlap,
            ruby=RubyPolicy(enabled=False),
        ).build(target, context)

    return render_karaoke(document, items, effect=effect, owner="parallel-example")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = build()
    result.document.save(args.output)
    print(f"{result.event_count} events; {len(result.diagnostics)} diagnostics")


if __name__ == "__main__":
    main()
