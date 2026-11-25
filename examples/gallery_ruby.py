"""Time a Japanese lyric and its ruby readings with the same note boundaries."""

import argparse
from pathlib import Path

from kara_templater import (
    Box,
    Color,
    Document,
    KaraokeEffects,
    Layout,
    Line,
    LyricScene,
    Style,
    Track,
    build_lyric_scene,
)


def build() -> LyricScene:
    doc = Document.create(
        width=720,
        height=405,
        styles=(
            Style(fontname="Noto Sans CJK JP", fontsize=66, outline=2, shadow=0),
        ),
    )
    doc.records.append(
        Line(start_time=600, end_time=3750, text=r"{\k75}星|ほし{\k30}の{\k210}声|こえ")
    )
    return build_lyric_scene(
        doc,
        tracks=(
            Track(
                id="lead",
                region=Box(35, 115, 650, 175),
                layout=Layout(alignment="center"),
                effects=(
                    KaraokeEffects(
                        highlight="utopia",
                        before_fill=Color.hex("#F4E7FF"),
                        after_fill=Color.hex("#E8A9FC"),
                        hook_feather=10,
                    ),
                ),
            ),
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    build().export(args.output, fps=30)


if __name__ == "__main__":
    main()
