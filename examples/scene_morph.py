"""E10: explicit contour correspondence, holes and text-to-path morphing.

uv run python -m examples.scene_morph output.ass
"""

import argparse
from dataclasses import replace
from pathlib import Path

from kara_templater import (
    CYAN,
    PINK,
    Document,
    Lifetime,
    MorphPath,
    PathObject,
    Scene,
    TextObject,
    Vec2,
    VectorPath,
    VisualState,
    resample_path,
    smooth_rate,
    text_to_path,
)


def build() -> Scene:
    # Same order: clockwise outer contour, counterclockwise hole.
    circle = VectorPath.circle(100)
    hole = VectorPath.circle(40).map(lambda p: Vec2(-p.x, p.y))
    ring = resample_path(VectorPath((*circle.contours, *hole.contours)), 64)
    square = VectorPath.polygon(
        Vec2(100, 0), Vec2(100, 100), Vec2(-100, 100), Vec2(-100, -100), Vec2(100, -100)
    )
    window = VectorPath.polygon(
        Vec2(-40, 0), Vec2(-40, 40), Vec2(40, 40), Vec2(40, -40), Vec2(-40, -40)
    )
    target = resample_path(VectorPath((*square.contours, *window.contours)), 64)
    shape = PathObject(
        id="ring",
        path=ring,
        lifetime=Lifetime(0, 5),
        state=VisualState(position=Vec2(440, 350), fill=CYAN),
        deform=MorphPath(target, start=1, duration=3, rate=smooth_rate),
    )
    letter = text_to_path(
        TextObject(
            id="glyph",
            text="B",
            font_size=180,
            lifetime=Lifetime(0, 5),
            state=VisualState(position=Vec2(730, 260), fill=PINK),
        )
    )
    # Preserve the glyph's contour correspondence while deliberately changing shape.
    stretched = letter.path.map(
        lambda point: Vec2(point.x * 1.5 + 0.12 * point.y, point.y * 0.75)
    )
    letter = replace(
        letter, deform=MorphPath(stretched, start=1, duration=3, rate=smooth_rate)
    )
    return Scene(Document.create()).add(shape, letter)


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
