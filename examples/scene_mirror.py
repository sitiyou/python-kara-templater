"""Signed group scale crosses zero while text, paths and their mask stay aligned.

uv run python -m examples.scene_mirror output.ass
"""

import argparse
from pathlib import Path

from kara_templater import (
    CYAN,
    PINK,
    Document,
    Lifetime,
    ObjectGroup,
    PathObject,
    RectangleClip,
    Scene,
    StatePatch,
    TextObject,
    Timeline,
    Tween,
    Vec2,
    VectorPath,
    VisualState,
    smooth_rate,
)


def build() -> Scene:
    lifetime = Lifetime(0, 5.5)
    timeline = Timeline().wait(0.5)
    for scale, duration, pause in (
        (0, 1, 0.1),
        (-1, 0.9, 0.5),
        (0, 1, 0.1),
        (1, 0.9, 0),
    ):
        timeline.play(
            Tween(StatePatch(scale=Vec2(scale, 1)), smooth_rate), duration=duration
        )
        timeline.wait(pause)
    word = TextObject(
        id="word",
        text="REFLECT",
        lifetime=lifetime,
        font_size=88,
        alignment=5,
        state=VisualState(rotation=15, fill=CYAN),
    )
    arrow = PathObject(
        id="arrow",
        lifetime=lifetime,
        path=VectorPath.polygon(
            Vec2(-90, 0),
            Vec2(60, 0),
            Vec2(60, -15),
            Vec2(100, 10),
            Vec2(60, 35),
            Vec2(60, 20),
            Vec2(-90, 20),
        ),
        state=VisualState(position=Vec2(0, 80), fill=PINK),
    )
    group = ObjectGroup(
        id="mirror",
        lifetime=lifetime,
        children=(word, arrow),
        state=VisualState(position=Vec2(640, 320), rotation=-10),
        animations=timeline.clips,
        clip=RectangleClip(-210, -100, 210, 130, space="local"),
    )
    caption = TextObject(
        id="caption",
        text="SCALE  1 → 0 → −1 → 0 → 1",
        alignment=5,
        font_size=30,
        lifetime=lifetime,
        state=VisualState(position=Vec2(640, 570)),
    )
    return Scene(Document.create()).add(group, caption)


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
