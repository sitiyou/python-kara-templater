"""Four animated filled-path booleans, with proper contours for outlines.

uv run python -m examples.scene_boolean output.ass
"""

import argparse
from math import cos, sin, tau
from pathlib import Path

from kara_templater import (
    CYAN,
    GREEN,
    PINK,
    WHITE,
    Document,
    Lifetime,
    PathBooleanOperation,
    PathFunction,
    PathObject,
    Scene,
    TextObject,
    Vec2,
    VectorPath,
    VisualState,
    path_boolean,
    smooth_rate,
)

STAR = VectorPath.polygon(
    *(
        Vec2(cos(index * tau / 10 - tau / 4), sin(index * tau / 10 - tau / 4))
        * (90 if index % 2 == 0 else 42)
        for index in range(10)
    )
)
CUTTER = VectorPath.circle(48)


def operation_shape(operation: PathBooleanOperation) -> PathFunction:
    def sample(path: VectorPath, time: float) -> VectorPath | None:
        progress = smooth_rate(min(1, max(0, (time - 0.5) / 4)))
        cutter = CUTTER.map(lambda point: point + Vec2(100 - 200 * progress, 0))
        return path_boolean(path, cutter, operation, max_points=256, max_work=100_000)

    return PathFunction(sample, max_points=256, breakpoints=(0.5, 4.5))


def build() -> Scene:
    scene = Scene(Document.create())
    lifetime = Lifetime(0, 5.5)
    operations: tuple[PathBooleanOperation, ...] = (
        "intersection",
        "union",
        "difference",
        "xor",
    )
    for index, (operation, color) in enumerate(
        zip(operations, (CYAN, PINK, WHITE, GREEN), strict=True)
    ):
        x = 180 + 300 * index
        scene.add(
            PathObject(
                id=operation,
                lifetime=lifetime,
                path=STAR,
                state=VisualState(position=Vec2(x, 350), fill=color, border=2),
                deform=operation_shape(operation),
            ),
            TextObject(
                id=f"label:{operation}",
                text=operation.upper(),
                lifetime=lifetime,
                alignment=5,
                font_size=24,
                state=VisualState(position=Vec2(x, 510), fill=color),
            ),
        )
    return scene.add(
        TextObject(
            id="title",
            text="PATH BOOLEANS • NONZERO WINDING • STANDARD ASS",
            lifetime=lifetime,
            alignment=5,
            font_size=28,
            state=VisualState(position=Vec2(640, 160)),
        )
    )


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
