"""Nonuniform parent scale, child rotation and local masks share one affine map.

uv run python -m examples.scene_affine output.ass
"""

import argparse
from pathlib import Path

from kara_templater import (
    CYAN,
    PINK,
    AnimationClip,
    Document,
    Lifetime,
    ObjectGroup,
    PathObject,
    RectangleClip,
    Scene,
    StatePatch,
    TextObject,
    Tween,
    Vec2,
    VectorPath,
    VisualState,
    smooth_rate,
)


def build() -> Scene:
    lifetime = Lifetime(0, 5)
    word = TextObject(
        id="word",
        text="AFFINE",
        font_size=90,
        alignment=7,
        lifetime=lifetime,
        state=VisualState(position=Vec2(-170, -60), rotation=20, fill=CYAN, border=1),
        clip=RectangleClip(0, -10, 280, 110, space="local"),
    )
    tile = PathObject(
        id="tile",
        lifetime=lifetime,
        path=VectorPath.rectangle(180, 70),
        state=VisualState(
            position=Vec2(-100, 70), rotation=-25, fill=PINK, opacity=0.5
        ),
        clip=RectangleClip(0, 0, 120, 70, space="local"),
    )
    group = ObjectGroup(
        id="affine-group",
        lifetime=lifetime,
        state=VisualState(position=Vec2(640, 330), scale=Vec2(1.6, 0.7), rotation=-20),
        animations=(
            AnimationClip(
                0.5, 4, Tween(StatePatch(rotation=25, skew=Vec2(0.25, 0)), smooth_rate)
            ),
        ),
        children=(word, tile),
    )
    caption = TextObject(
        id="caption",
        text="NONUNIFORM SCALE + ROTATION + LOCAL MASK",
        alignment=5,
        font_size=28,
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
