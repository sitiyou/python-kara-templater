"""E09: independently colored fill/outline in a fixed screen-space gradient.

uv run python -m examples.scene_gradient output.ass
"""

import argparse
from pathlib import Path

from kara_templater import (
    BLUE,
    CYAN,
    PINK,
    WHITE,
    AnimationClip,
    ColorRamp,
    ColorStop,
    Document,
    Lifetime,
    LinearGradient,
    Scene,
    StatePatch,
    TextObject,
    Tween,
    Vec2,
    VisualState,
    echoes,
)


def build() -> Scene:
    gradient = LinearGradient(
        fill=ColorRamp(
            (ColorStop(320, CYAN), ColorStop(640, PINK), ColorStop(960, WHITE))
        ),
        outline=ColorRamp((ColorStop(320, BLUE), ColorStop(960, PINK))),
    )
    word = TextObject(
        id="gradient",
        text="GRADIENT",
        font_size=112,
        lifetime=Lifetime(0, 5),
        alignment=5,
        state=VisualState(position=Vec2(580, 270), border=3),
        material=gradient,
        animations=(AnimationClip(0.5, 4, Tween(StatePatch(position=Vec2(700, 270)))),),
    )
    scene = Scene(Document.create()).add(word)
    palette = ColorRamp((ColorStop(0, CYAN), ColorStop(4, PINK)))
    for index, letter in enumerate("COLOR"):
        position = Vec2(440 + index * 75, 470)
        glyph = TextObject(
            id=f"letter:{index}",
            text=letter,
            font_size=72,
            alignment=5,
            lifetime=Lifetime(0, 4.7),
            state=VisualState(position=position, fill=palette.at(index)),
            animations=(
                AnimationClip(
                    0.5, 3.5, Tween(StatePatch(position=position + Vec2(100, 0)))
                ),
            ),
        )
        scene.add(*echoes(glyph, count=3, spacing=0.08, opacity=0.35), glyph)
    return scene


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
