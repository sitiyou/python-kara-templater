"""One lyric line with three alternating colors, configured entirely in Python.

python -m examples.track_colors output.hook
Use --effect examples/track_colors.py with the CLI to process an ASS containing
ABCABC timed as six syllables. The builder produces a normal Scene using the common lyric frontend.
"""

import argparse
from pathlib import Path

from examples._lyrics import document
from kara_templater import (
    BLUE,
    GREEN,
    RED,
    Document,
    Layout,
    LyricHighlights,
    LyricLine,
    LyricRule,
    ScalePulse,
    Scene,
    StatePatch,
    Track,
    Vec2,
    prepare_tracks,
)


def color(line: LyricLine) -> LyricLine:
    """Choose a sung color for each authored syllable."""
    palette = (RED, GREEN, BLUE)
    return LyricHighlights.from_singing(
        StatePatch(fill=RED),
        segment_colors={
            (index, segment): palette[index % len(palette)]
            for index, unit in enumerate(line.layout.lyrics.units)
            for segment in range(len(unit.segments))
        },
    )(line)


def sample() -> Document:
    source = document(fontname="DejaVu Sans", text="ABCABC")
    source.lines[0].text = "".join(r"{\k50}" + letter for letter in "ABCABC")
    return source


TRACKS = (
    Track(
        id="colors",
        source=lambda source: source.text == "ABCABC",
        layout=Layout(position=Vec2(0, 180), alignment="center"),
        preview=0,
        tail=0,
        effects=(
            LyricRule("syllable", "singing", ScalePulse(peak=1.08)),
            color,
        ),
    ),
)


def build(document: Document) -> Scene:
    """Bind source lyrics to the same objects and compiler as ordinary Scenes."""
    return prepare_tracks(document, tracks=TRACKS, owner="track-colors")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    build(sample()).export(args.output)


if __name__ == "__main__":
    main()
