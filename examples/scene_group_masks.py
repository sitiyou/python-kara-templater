"""A moving group mask clips text and nested decorations in shared coordinates.

uv run python -m examples.scene_group_masks output.ass
"""

import argparse
from pathlib import Path

from kara_templater import (
    CYAN,
    PINK,
    WHITE,
    AnimationClip,
    Document,
    Lifetime,
    ObjectGroup,
    PathFunction,
    PathObject,
    RectangleClip,
    Scene,
    StatePatch,
    TextObject,
    Tween,
    Vec2,
    VectorClip,
    VectorPath,
    VisualState,
    smooth_rate,
)


def spotlight(path: VectorPath, time: float) -> VectorPath:
    progress = smooth_rate(min(1, time / 4))
    return path.map(lambda point: point + Vec2(-180 + 360 * progress, 0))


def build() -> Scene:
    lifetime = Lifetime(0, 5)
    text = TextObject(
        id="text",
        text="ONE SHARED MASK",
        font_size=64,
        alignment=5,
        lifetime=lifetime,
    )
    bars = ObjectGroup(
        id="bars",
        lifetime=lifetime,
        clip=RectangleClip(-240, 55, 240, 80, space="local"),
        children=tuple(
            PathObject(
                id=f"bar:{index}",
                lifetime=lifetime,
                path=VectorPath.rectangle(150, 70),
                state=VisualState(position=Vec2(-240 + index * 165, 35), fill=color),
            )
            for index, color in enumerate((PINK, CYAN, WHITE))
        ),
    )
    group = ObjectGroup(
        id="spotlight",
        lifetime=lifetime,
        children=(text, bars),
        state=VisualState(position=Vec2(640, 330), rotation=-10),
        animations=(
            AnimationClip(0.5, 4, Tween(StatePatch(rotation=10), smooth_rate)),
        ),
        clip=VectorClip(
            VectorPath.circle(140),
            space="local",
            deform=PathFunction(spotlight, max_points=13, breakpoints=(4,)),
        ),
    )
    caption = TextObject(
        id="caption",
        text="ONE MASK • GROUP CLOCK • NESTED INTERSECTION",
        alignment=5,
        font_size=27,
        lifetime=lifetime,
        state=VisualState(position=Vec2(640, 570), fill=CYAN),
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
