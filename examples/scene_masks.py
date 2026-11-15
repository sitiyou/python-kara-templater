"""Local rotating crop, independent moving spotlight, and vector-masked gradient.

uv run python -m examples.scene_masks output.ass
"""

import argparse
from pathlib import Path

from kara_templater import (
    CYAN,
    PINK,
    AnimationClip,
    ColorRamp,
    ColorStop,
    Document,
    Lifetime,
    LinearGradient,
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
)


def spotlight(path: VectorPath, time: float) -> VectorPath | None:
    if time < 0.5 or time >= 4.5:
        return None
    progress = (time - 0.5) / 4
    return path.map(lambda point: point + Vec2(200 + 800 * progress, 390))


def build() -> Scene:
    lifetime = Lifetime(0, 5)
    crop = RectangleClip(0, 0, 300, 90, space="local")
    moving = ObjectGroup(
        id="moving",
        lifetime=lifetime,
        state=VisualState(position=Vec2(160, 130)),
        children=(
            PathObject(
                id="frame",
                lifetime=lifetime,
                path=VectorPath.rectangle(300, 90),
                state=VisualState(fill=CYAN, opacity=0.12),
            ),
            TextObject(
                id="local",
                lifetime=lifetime,
                text="LOCAL MASK",
                font_size=72,
                clip=crop,
            ),
        ),
        animations=(
            AnimationClip(
                0.5,
                3,
                Tween(
                    StatePatch(
                        position=Vec2(650, 170), rotation=15, scale=Vec2(1.1, 1.1)
                    )
                ),
            ),
        ),
    )
    screen = TextObject(
        id="screen",
        lifetime=lifetime,
        text="SCREEN SPOTLIGHT",
        font_size=72,
        state=VisualState(position=Vec2(260, 350), fill=PINK, border=2),
        clip=VectorClip(
            VectorPath.circle(85),
            deform=PathFunction(spotlight, max_points=13, breakpoints=(0.5, 4.5)),
        ),
    )
    gradient = TextObject(
        id="gradient",
        lifetime=lifetime,
        text="GRADIENT MASK",
        font_size=72,
        state=VisualState(position=Vec2(260, 530), border=2),
        clip=VectorClip(
            VectorPath.circle(45).map(lambda p: Vec2(640 + p.x * 8, 570 + p.y))
        ),
        material=LinearGradient(
            fill=ColorRamp((ColorStop(260, CYAN), ColorStop(1000, PINK)))
        ),
    )
    return Scene(Document.create()).add(moving, screen, gradient)


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
