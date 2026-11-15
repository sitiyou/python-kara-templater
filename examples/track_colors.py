"""One lyric line with three alternating colors, configured entirely in Python.

python -m examples.track_colors output.ass
The same tracks can be used with Document.load("input.ass").
"""

import argparse
from pathlib import Path

from kara_templater import (
    BLUE,
    GREEN,
    RED,
    WHITE,
    Body,
    LineMatch,
    Overlay,
    PaintStyle,
    SingingPulseAnimation,
    TextSpan,
    TextStyle,
    Track,
    prepare_tracks,
)

from ._lyrics import document

tracks = (
    Track(
        source=LineMatch(text="ABCABC"),
        body=Body(
            style=TextStyle(fill=WHITE),
            spans=tuple(
                TextSpan(
                    index,
                    index + 1,
                    overlay=PaintStyle(fill=(RED, GREEN, BLUE)[index % 3]),
                )
                for index in range(6)
            ),
        ),
        overlay=Overlay(),
        animations=(SingingPulseAnimation(peak=1.08),),
    ),
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = prepare_tracks(
        document(fontname="DejaVu Sans", text="ABCABC"), tracks=tracks, mode="native"
    ).compile()
    result.document.save(args.output)
    print(f"{result.event_count} events → {args.output}")


if __name__ == "__main__":
    main()
