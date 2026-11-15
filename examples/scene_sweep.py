"""E11: soft fill/outline sweep over an independent, unsliced whole-word glow.

uv run python -m examples.scene_sweep output.ass
"""

import argparse
from dataclasses import replace
from pathlib import Path

from kara_templater import (
    PINK,
    WHITE,
    Color,
    Document,
    Lifetime,
    Scene,
    SoftSweep,
    TextObject,
    Vec2,
    VisualState,
)


def build() -> Scene:
    word = TextObject(
        id="lyrics",
        text="SOFT SWEEP",
        font_size=108,
        alignment=5,
        lifetime=Lifetime(0, 5),
        state=VisualState(position=Vec2(640, 340), border=3),
        material=SoftSweep(
            left=240,
            right=1040,
            start=1,
            duration=3,
            fill=(WHITE, PINK),
            outline=(PINK, Color.hex("#C92564")),
            width=24,
            outline_width=36,
        ),
    )
    # This glow remains pink throughout; it does not smear the moving color front.
    glow = replace(
        word.copy(id="glow"),
        material=None,
        layer=-1,
        state=replace(
            word.state, fill=PINK, outline=PINK, border=7, blur=9, opacity=0.6
        ),
    )
    return Scene(Document.create()).add(glow, word)


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
