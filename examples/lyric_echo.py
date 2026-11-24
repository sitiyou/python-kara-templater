"""Onset echoes without per-character loops or hand-authored animation times.

uv run python -m examples.lyric_echo build/lyric-echo.ass
"""

import argparse
from pathlib import Path

from kara_templater import (
    CYAN,
    Box,
    Document,
    Layout,
    Line,
    LyricEcho,
    LyricHighlights,
    LyricScene,
    StatePatch,
    Style,
    Track,
    Vec2,
    build_lyric_scene,
)


def build() -> LyricScene:
    """Original short/held-note fixture with a three-copy vertical echo."""
    document = Document.create(
        width=1280,
        height=720,
        styles=(Style(fontname="DejaVu Sans", fontsize=64, outline=2, shadow=0),),
    )
    document.records.append(
        Line(
            start_time=1000,
            end_time=5000,
            text=r"{\k25}We {\k25}can {\k50}make {\k100}each {\k200}note shine",
        )
    )
    return build_lyric_scene(
        document,
        tracks=(
            Track(
                id="main",
                region=Box(80, 480, 1120, 180),
                layout=Layout(alignment="center"),
                effects=(
                    LyricHighlights.from_timing(StatePatch(fill=CYAN)),
                    LyricEcho(
                        count=3,
                        offset=Vec2(0, -10),
                        duration=0.5,
                        paint=StatePatch(fill=CYAN),
                    ),
                ),
            ),
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = build().ass.compile(native_tweens=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(result.document.dumps(), encoding="utf-8-sig")
    print(f"{result.event_count} events, {result.byte_count} bytes")


if __name__ == "__main__":
    main()
