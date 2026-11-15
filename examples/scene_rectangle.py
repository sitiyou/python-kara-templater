"""A shared moving rectangular window and its inverse, emitted as standard ASS.

uv run python -m examples.scene_rectangle output.ass
"""

import argparse
from math import cos, tau
from pathlib import Path

from kara_templater import (
    CYAN,
    PINK,
    Document,
    Lifetime,
    RectangleClip,
    RectangleFunction,
    Scene,
    TextObject,
    Vec2,
    VisualState,
)


def window(time: float) -> tuple[float, float, float, float] | None:
    center = 640 - 300 * cos(tau * time / 5.5)
    return center - 90, 0, center + 90, 720


def build() -> Scene:
    scene = Scene(Document.create())
    for index, (color, inverse) in enumerate(((CYAN, True), (PINK, False))):
        scene.add(
            TextObject(
                id=f"window:{index}",
                text="RECTANGLE",
                lifetime=Lifetime(0, 5.5),
                font_size=100,
                alignment=5,
                state=VisualState(
                    position=Vec2(640, 340), fill=color, outline=color, border=2
                ),
                clip=RectangleClip(
                    0, 0, 1, 1, inverse=inverse, deform=RectangleFunction(window)
                ),
            )
        )
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
