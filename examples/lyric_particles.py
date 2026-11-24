"""Measured sweep-front sparkles or falling petals, with no manual emission loop.

uv run python -m examples.lyric_particles build/sparkles.ass --kind sparkle
"""

import argparse
from pathlib import Path
from typing import Literal

from kara_templater import (
    CYAN,
    PINK,
    Box,
    Document,
    DriftOut,
    Layout,
    Line,
    LyricHighlights,
    LyricParticles,
    LyricRule,
    LyricScene,
    Petal,
    Sparkle,
    StatePatch,
    Style,
    Track,
    build_lyric_scene,
)


def build(kind: Literal["sparkle", "petal"] = "sparkle") -> LyricScene:
    """Compile shared original lyrics with short and sustained notes."""
    doc = Document.create(
        width=1280,
        height=720,
        styles=(Style(fontname="DejaVu Sans", fontsize=64, outline=2, shadow=0),),
    )
    doc.records.append(
        Line(
            start_time=1000,
            end_time=5000,
            text=r"{\k25}We {\k25}can {\k50}make {\k100}each {\k200}note shine",
        )
    )
    particle = Sparkle(size=4) if kind == "sparkle" else Petal(size=5)
    return build_lyric_scene(
        doc,
        tracks=(
            Track(
                id="main",
                region=Box(80, 480, 1120, 180),
                layout=Layout(alignment="center"),
                effects=(
                    *(
                        ()
                        if kind == "sparkle"
                        else (
                            LyricRule(
                                "character",
                                "after_timing",
                                DriftOut(),
                                duration=0.5,
                                offset=0.12,
                            ),
                        )
                    ),
                    LyricHighlights.from_timing(
                        StatePatch(fill=CYAN if kind == "sparkle" else PINK)
                    ),
                    LyricParticles(factory=particle, rate=16, seed=42),
                ),
            ),
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--kind", choices=("sparkle", "petal"), default="sparkle")
    args = parser.parse_args()
    scene = build(args.kind)
    if args.output.suffix == ".hook":
        args.output.parent.mkdir(parents=True, exist_ok=True)
        scene.export(args.output, fps=60)
        return
    result = scene.ass.compile()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(result.document.dumps(), encoding="utf-8-sig")
    print(f"{result.event_count} events, {result.byte_count} bytes")


if __name__ == "__main__":
    main()
