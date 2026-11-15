"""E07: deterministic text-outline perturbation with an author-defined envelope.

uv run python -m examples.scene_outlines output.ass
"""

import argparse
from dataclasses import replace
from math import sin, tau
from pathlib import Path
from random import Random

from kara_templater import (
    CYAN,
    Document,
    Lifetime,
    PathFunction,
    Scene,
    TextObject,
    Vec2,
    VectorPath,
    VisualState,
    text_to_path,
)


def build() -> Scene:
    word = TextObject(
        id="wave",
        text="WAVE",
        font_size=120,
        lifetime=Lifetime(0, 5),
        state=VisualState(position=Vec2(430, 280), fill=CYAN),
    )
    outline = text_to_path(word)
    random = Random(17)
    phases = (random.uniform(0, tau), random.uniform(0, tau))

    def ripple(path: VectorPath, time: float) -> VectorPath:
        # Spatially continuous perturbation keeps shared contour endpoints joined.
        envelope = sin(max(0, min(1, (time - 1) / 3)) * tau / 2) ** 2
        return path.map(
            lambda point: (
                point
                + Vec2(
                    4 * envelope * sin(point.y * 0.08 + time * 11 + phases[0]),
                    4 * envelope * sin(point.x * 0.06 + time * 9 + phases[1]),
                )
            )
        )

    return Scene(Document.create()).add(
        replace(
            outline,
            deform=PathFunction(
                ripple,
                max_points=outline.path.point_count,
                breakpoints=(1, 4),
            ),
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
