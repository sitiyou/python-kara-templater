"""Explicit continuous ASS interpolation for a text entrance, hold and exit.

uv run python -m examples.scene_native_tween output.ass
"""

import argparse
from pathlib import Path

from kara_templater import (
    CYAN,
    PINK,
    Document,
    Lifetime,
    Scene,
    StatePatch,
    TextObject,
    Timeline,
    Tween,
    Vec2,
    VisualState,
)


def build() -> Scene:
    title = TextObject(
        id="title",
        text="CONTINUOUS",
        alignment=5,
        font_size=80,
        lifetime=Lifetime(0, 5),
        state=VisualState(
            position=Vec2(640, 360),
            scale=Vec2(0.8, 0.8),
            rotation=-8,
            fill=CYAN,
            opacity=0,
        ),
        animations=(
            Timeline()
            .wait(0.5)
            .play(
                Tween(
                    StatePatch(
                        scale=Vec2(1, 1), rotation=0, fill=PINK, opacity=1, border=2
                    )
                ),
                duration=2,
            )
            .wait(1)
            .play(
                Tween(
                    StatePatch(scale=Vec2(0.8, 0.8), rotation=8, fill=CYAN, border=0)
                ),
                Tween(StatePatch(opacity=0)),
                duration=1,
            )
            .clips
        ),
    )
    return Scene(Document.create()).add(title)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    result = build().ass.compile(native_tweens=True)
    result.document.save(parser.parse_args().output)
    print(
        f"{result.event_count} events, {result.peak_active} active, {result.byte_count} bytes"
    )


if __name__ == "__main__":
    main()
