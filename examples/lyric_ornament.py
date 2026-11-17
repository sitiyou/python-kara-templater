"""Independent text/ornament exit clocks, inspired by the P70 stationary arch.

uv run python -m examples.lyric_ornament build/lyric-ornament.ass
"""

import argparse
from dataclasses import replace
from pathlib import Path

from kara_templater import (
    CYAN,
    Box,
    Document,
    FadeIn,
    FadeOut,
    Layout,
    Lifetime,
    Line,
    LyricHighlights,
    LyricLine,
    LyricRule,
    LyricScene,
    LyricTarget,
    PathObject,
    StatePatch,
    Style,
    TimeSpan,
    Track,
    Vec2,
    VectorPath,
    VisualState,
    prepare_tracks,
)


def row_end(line: LyricLine, target: LyricTarget) -> tuple[TimeSpan, ...]:
    """A reusable custom anchor: all characters share this row's singing end."""
    end = max(span.end for span in line.query("line")[0].singing) + target.delay
    return (TimeSpan(end, end),)


def arch(line: LyricLine) -> LyricLine:
    """Static dots, with right-to-left fades on their own source-relative clocks."""
    box = line.layout.body.bounds
    end = row_end(line, line.query("line")[0])[0].end
    dots = []
    for index in range(9):
        progress = index / 8
        fade = end + 0.3 + (8 - index) * 0.07
        dots.append(PathObject(
            id=f"{line.id}/arch:{index}",
            lifetime=Lifetime(line.time_origin, fade + 0.3),
            path=VectorPath.circle(2),
            state=VisualState(
                position=Vec2(box.left - 10 + progress * (box.width + 20),
                              box.top - 10 - 25 * (1 - (2 * progress - 1) ** 2)),
                fill=CYAN, blur=0.5,
            ),
        ).animate(FadeOut(), at=fade - line.time_origin, duration=0.3))
    # Preparation discovers these lifetimes and reserves the layout interval.
    return replace(line, children=(*line.children, *dots)).schedule(
        LyricRule("character", row_end, FadeOut(), duration=0.28, stagger=0.06),
    )


def build() -> LyricScene:
    document = Document.create(width=640, height=360, styles=(
        Style(fontname="DejaVu Sans", fontsize=48, outline=2, shadow=0),
    ))
    document.records.append(Line(start_time=1000, end_time=3000,
                                 text=r"{\k25}A{\k25}B{\k50}C{\k100}D"))
    return prepare_tracks(document, tracks=(Track(
        id="main", region=Box(80, 190, 480, 120), layout=Layout(alignment="center"),
        effects=(
            LyricHighlights.from_singing(StatePatch(fill=CYAN)), arch,
            LyricRule("line", "enter", FadeIn(), duration=0.2),
        ),
    ),))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    build().compile(native_tweens=True).document.save(args.output)


if __name__ == "__main__":
    main()
