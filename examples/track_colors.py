"""One lyric line with three alternating colors, configured entirely in Python.

python -m examples.track_colors output.ass
Use --effect examples/track_colors.py with the CLI to process an ASS containing
ABCABC. The builder produces a normal Scene using the common lyric frontend.
"""

import argparse
from pathlib import Path

from examples._lyrics import document
from kara_templater import (
    BLUE,
    GREEN,
    RED,
    Color,
    Document,
    Layout,
    LyricLine,
    LyricRule,
    LyricSweep,
    LyricTarget,
    ScalePulse,
    Scene,
    Track,
    Vec2,
    prepare_tracks,
)


def color(line: LyricLine, target: LyricTarget) -> Color:
    """Choose by shaped cluster, without defining clocks or splitting source text."""
    index = line.query(target.role).index(target)
    return (RED, GREEN, BLUE)[index % 3]


TRACKS = (
    Track(
        id="colors",
        source=lambda source: source.text == "ABCABC",
        layout=Layout(position=Vec2(0, 180), alignment="center"),
        preview=0,
        tail=0,
        factory=LyricSweep(fill=color, width=0).apply,
        animations=(LyricRule("syllable", "singing", ScalePulse(peak=1.08)),),
    ),
)


def build(document: Document) -> Scene:
    """Bind source lyrics to the same objects and compiler as ordinary Scenes."""
    return prepare_tracks(document, tracks=TRACKS, owner="track-colors")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = build(document(fontname="DejaVu Sans", text="ABCABC")).compile()
    result.document.save(args.output)
    print(f"{result.event_count} events → {args.output}")


if __name__ == "__main__":
    main()
