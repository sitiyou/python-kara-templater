"""Disjoint, priority, and layered highlights on the same lyric segment.

Run from a checkout: python -m examples.parallel_tracks output.ass
Edit highlight clocks, regions, styles, and opacity without splitting the lyrics.
"""

import argparse
from pathlib import Path

from kara_templater import (
    BLACK,
    Body,
    Color,
    DisplayWindow,
    Document,
    HighlightStyle,
    HighlightTrack,
    KaraokeItem,
    KaraokeLine,
    LaidOutLine,
    LineMatch,
    Overlay,
    Paint,
    PaintStyle,
    Region,
    Scene,
    Segment,
    SingingPass,
    Style,
    TextSpan,
    TextStyle,
    TextUnit,
    Track,
    prepare_tracks,
)

SWEEP_CYAN = Color.hex("#33ddff")
ECHO_PINK = Color.hex("#ff5599")


def disjoint(layout: LaidOutLine) -> tuple[HighlightTrack, ...]:
    box = layout.units[0].box
    whole = Region(box.left, box.right)
    return (
        HighlightTrack(
            "left", 0, (SingingPass(1000, 2400, Region(whole.left, whole.center)),)
        ),
        HighlightTrack(
            "right", 0, (SingingPass(1000, 2400, Region(whole.center, whole.right)),)
        ),
    )


def overlapping(layout: LaidOutLine) -> tuple[HighlightTrack, ...]:
    box = layout.units[0].box
    whole = Region(box.left, box.right)
    return (
        HighlightTrack("main", 0, (SingingPass(1000, 2400, whole),)),
        HighlightTrack(
            "echo", 0, (SingingPass(1200, 2000, whole),), end_behavior="hide"
        ),
    )


def build() -> Scene:
    styles = tuple(
        Style(name=name, fontname="DejaVu Sans", fontsize=52, align=8, margin_v=margin)
        for name, margin in (("regions", 60), ("priority", 200), ("layer", 340))
    )
    document = Document.create(width=640, height=480, styles=styles)
    source = KaraokeLine((TextUnit("Karaoke", (Segment(1000, 2400),)),))
    items = tuple(
        KaraokeItem(style.name, source, style.name, DisplayWindow(0, 3000))
        for style in styles
    )
    configurations = []
    for mode in ("regions", "priority", "layer"):
        opacity = 0.5 if mode == "layer" else 1.0
        highlight_styles = (
            ()
            if mode == "regions"
            else (
                HighlightStyle("main", Paint(SWEEP_CYAN, opacity=opacity)),
                HighlightStyle("echo", Paint(ECHO_PINK, opacity=opacity), priority=10),
            )
        )
        configurations.append(
            Track(
                source=LineMatch(style=mode),
                body=Body(
                    style=TextStyle(fill="#a0a0a0", stroke=BLACK, stroke_width=0),
                    spans=(TextSpan(4, 7, overlay=PaintStyle(fill=ECHO_PINK)),),
                ),
                overlay=Overlay(
                    style=PaintStyle(fill=SWEEP_CYAN),
                    highlights=disjoint if mode == "regions" else overlapping,
                    styles=highlight_styles,
                    overlap="union" if mode == "regions" else mode,
                ),
            )
        )
    return prepare_tracks(
        document,
        items,
        tracks=tuple(configurations),
        mode="native",
        owner="parallel-example",
    ).scene


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = build().compile()
    result.document.save(args.output)
    print(f"{result.event_count} events; {result.peak_active} active")


if __name__ == "__main__":
    main()
