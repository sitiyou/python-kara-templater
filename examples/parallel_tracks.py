"""Compare three simultaneous sweep policies on one multi-character segment.

Run: python -m examples.parallel_tracks /tmp/parallel.ass
Rows, top to bottom: disjoint regions, priority override, translucent layers.
All rows preserve the same source timing and character layout.
"""

import argparse
from pathlib import Path

from kara_templater import (
    BLACK,
    Body,
    Color,
    DisplayWindow,
    Document,
    Effect,
    HighlightTrack,
    KaraokeItem,
    KaraokeLine,
    Lyrics,
    Paint,
    Region,
    Segment,
    SingingPass,
    Style,
    TextUnit,
    TrackStyle,
    render_karaoke,
)
from kara_templater.ass import EVENT_FORMAT, STYLE_FORMAT

SWEEP_CYAN = Color.hex("#33ddff")
ECHO_PINK = Color.hex("#ff5599")


class ParallelSweeps(Effect):
    def compose(self):
        yield Lyrics(Body(fill="#a0a0a0", stroke=BLACK, stroke_width=0, opacity=1))

    def configure(self):
        self.body.text_range(4, 7).style.sung.fill = ECHO_PINK
        mode = self.source.style
        opacity = 0.5 if mode == "layer" else 1
        track_styles = (
            ()
            if mode == "regions"
            else (
                TrackStyle("main", Paint(SWEEP_CYAN, opacity=opacity), 0),
                TrackStyle("echo", Paint(ECHO_PINK, opacity=opacity), 10),
            )
        )
        self.text.sweep(
            fill=SWEEP_CYAN,
            tracks=self.tracks,
            track_styles=track_styles,
            overlap="union" if mode == "regions" else mode,
        )

    def tracks(self, layout):
        box = layout.units[0].box
        whole = Region(box.left, box.right)
        if self.source.style == "regions":
            return (
                HighlightTrack(
                    "left",
                    0,
                    (SingingPass(1000, 2400, Region(whole.left, whole.center)),),
                ),
                HighlightTrack(
                    "right",
                    0,
                    (SingingPass(1000, 2400, Region(whole.center, whole.right)),),
                ),
            )
        return (
            HighlightTrack("main", 0, (SingingPass(1000, 2400, whole),)),
            HighlightTrack(
                "echo", 0, (SingingPass(1200, 2000, whole),), end_behavior="hide"
            ),
        )


def build():
    styles = tuple(
        Style(name=name, fontname="DejaVu Sans", fontsize=52, align=8, margin_v=margin)
        for name, margin in (("regions", 60), ("priority", 200), ("layer", 340))
    )
    document = Document.parse(
        "[Script Info]\nPlayResX: 640\nPlayResY: 480\n"
        "ScaledBorderAndShadow: yes\n[V4+ Styles]\nFormat: "
        + STYLE_FORMAT
        + "\n"
        + "\n".join(style.serialize() for style in styles)
        + "\n[Events]\nFormat: "
        + EVENT_FORMAT
        + "\n"
    )
    # Colour boundaries and sweep tracks do not split this singing segment.
    source = KaraokeLine((TextUnit("Karaoke", (Segment(1000, 2400),)),))
    items = tuple(
        KaraokeItem(style.name, source, style.name, DisplayWindow(0, 3000))
        for style in styles
    )
    return render_karaoke(
        document, items, effect=ParallelSweeps, owner="parallel-example"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = build()
    result.document.save(args.output)
    print(f"{result.event_count} events; {len(result.diagnostics)} diagnostics")


if __name__ == "__main__":
    main()
