"""Track lyric styling and scene decorations share one standard-ASS composition.

uv run python -m examples.scene_tracks output.ass
"""

import argparse
from pathlib import Path

from kara_templater import (
    CYAN,
    PINK,
    WHITE,
    AnimationClip,
    Blur,
    Body,
    Document,
    Lifetime,
    Line,
    LineMatch,
    MoveAlong,
    Overlay,
    PaintStyle,
    PathObject,
    Ruby,
    Scene,
    SingingPulseAnimation,
    SingleLine,
    StatePatch,
    Style,
    TextObject,
    TextStyle,
    Track,
    Tween,
    Vec2,
    VectorPath,
    VisualState,
    echoes,
    prepare_karaoke,
)


def build() -> Scene:
    document = Document.create(
        styles=(Style(fontname="DejaVu Sans", fontsize=80, align=5, shadow=0),)
    )
    document.records.append(
        Line(
            text=r"{\k100}Sing |sing{\k100}with |with{\k100}me|me",
            start_time=1000,
            end_time=4000,
        )
    )
    lyric = Track(
        source=LineMatch(),
        body=Body(
            style=TextStyle(fill=WHITE, blur=Blur(color=PINK, radius=4, width=4))
        ),
        ruby=Ruby(),
        overlay=Overlay(style=PaintStyle(fill=CYAN)),
        layout=SingleLine(position=(640, 360)),
        animations=(SingingPulseAnimation(peak=1.08),),
    )
    scene = prepare_karaoke(document, tracks=(lyric,)).scene
    orbit = PathObject(
        id="orbit",
        lifetime=Lifetime(0, 5),
        path=VectorPath.circle(7),
        state=VisualState(position=Vec2(640, 360), fill=PINK),
        animations=(
            AnimationClip(0, 5, MoveAlong(VectorPath.circle(250).contours[0])),
        ),
    )
    caption = TextObject(
        id="caption",
        text="TRACK + SCENE",
        alignment=5,
        font_size=30,
        lifetime=Lifetime(0, 5),
        state=VisualState(position=Vec2(640, 540), fill=CYAN, opacity=0),
        animations=(
            AnimationClip(0, 0.5, Tween(StatePatch(opacity=1))),
            AnimationClip(4.5, 0.5, Tween(StatePatch(opacity=0))),
        ),
    )
    return scene.add(*echoes(orbit, count=5, spacing=0.08, opacity=0.6), orbit, caption)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    result = build().compile()
    result.document.save(parser.parse_args().output)
    print(
        f"{result.event_count} events, {result.peak_active} active, {result.byte_count} bytes"
    )


if __name__ == "__main__":
    main()
