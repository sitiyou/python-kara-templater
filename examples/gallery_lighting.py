"""A timed feathered wipe, a tunable scanline, and two halo colors."""

import argparse
from pathlib import Path

from kara_templater import (
    Box,
    Color,
    Document,
    Glow,
    KaraokeEffects,
    Layout,
    Line,
    LyricScene,
    PaintInput,
    Style,
    Track,
    build_lyric_scene,
)


def build() -> LyricScene:
    doc = Document.create(
        width=720,
        height=405,
        styles=(
            Style(fontname="Noto Sans CJK JP", fontsize=62, bold=True, outline=2, shadow=0),
        ),
    )
    doc.records.append(
        Line(
            start_time=500,
            end_time=3800,
            text=r"{\k45}夜空{\k35}に{\k55}響く{\k195}光の中",
        )
    )
    lighting = KaraokeEffects(
        highlight="utopia_scanline",
        before_fill=Color.hex("#CCD7FF"),
        after_fill=Color.hex("#FFD998"),
        base_glow=Glow(Color.hex("#5A53EF"), border=7, blur=8),
        glow=Glow(Color.hex("#ED721D"), border=7, blur=8),
        hook_feather=12,
        scanline_width=22,
        scanline_softness=8,
        scanline_color=PaintInput("scanline_color", Color.hex("#FFF7E6")),
        scanline_strength=PaintInput("scanline_strength", 0.85),
    )
    return build_lyric_scene(
        doc,
        tracks=(
            Track(
                id="lead",
                region=Box(25, 138, 670, 129),
                layout=Layout(alignment="center"),
                effects=(lighting,),
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
