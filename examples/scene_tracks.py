"""Track lyric styling and scene decorations share one standard-ASS composition.

uv run python -m examples.scene_tracks output.ass
The 320x180 viewport and explicit coverage budget keep pixel-output cost visible.
"""

import argparse
from pathlib import Path

from examples.scene_coverage_tracks import BUDGET, paint
from kara_templater import (
    CYAN,
    PINK,
    AnimationClip,
    Document,
    Layout,
    Lifetime,
    Line,
    LyricRule,
    MoveAlong,
    PathObject,
    ScalePulse,
    Scene,
    StatePatch,
    Style,
    TextObject,
    Track,
    Tween,
    Vec2,
    VectorPath,
    VisualState,
    echoes,
    prepare_tracks,
)


def build() -> Scene:
    document = Document.create(
        width=320,
        height=180,
        styles=(
            Style(fontname="DejaVu Sans", fontsize=20, align=5, shadow=0, outline=0.5),
        ),
    )
    document.records.append(
        Line(
            text=r"{\k100}Sing |sing{\k100}with |with{\k100}me|me",
            start_time=1000,
            end_time=4000,
        )
    )
    lyric = Track(
        id="main",
        layout=Layout(position=Vec2(0, 70), alignment="center"),
        preview=0,
        tail=0,
        animations=(LyricRule("syllable", "singing", ScalePulse(peak=1.08)),),
        factory=paint,
    )
    scene = prepare_tracks(document, tracks=(lyric,))
    orbit = PathObject(
        id="orbit",
        lifetime=Lifetime(0, 5),
        path=VectorPath.circle(1.75),
        state=VisualState(position=Vec2(160, 90), fill=PINK),
        animations=(
            AnimationClip(0, 5, MoveAlong(VectorPath.circle(62.5).contours[0])),
        ),
    )
    caption = TextObject(
        id="caption",
        text="TRACK + SCENE",
        alignment=5,
        font_size=12,
        lifetime=Lifetime(0, 5),
        state=VisualState(position=Vec2(160, 145), fill=CYAN, opacity=0),
        animations=(
            AnimationClip(0, 0.5, Tween(StatePatch(opacity=1))),
            AnimationClip(4.5, 0.5, Tween(StatePatch(opacity=0))),
        ),
    )
    return scene.add(*echoes(orbit, count=5, spacing=0.08, opacity=0.6), orbit, caption)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    result = build().compile(budget=BUDGET)
    result.document.save(parser.parse_args().output)
    print(
        f"{result.event_count} events, {result.peak_active} active, {result.byte_count} bytes"
    )


if __name__ == "__main__":
    main()
