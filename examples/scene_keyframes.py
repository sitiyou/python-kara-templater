"""State keyframes, parallel rotation and a custom easing curve; standard ASS.

uv run python -m examples.scene_keyframes output.ass
"""

import argparse
from pathlib import Path

from kara_templater import (
    CYAN,
    PINK,
    Document,
    Lifetime,
    PathObject,
    Scene,
    StateKeyframe,
    StatePatch,
    Timeline,
    Tween,
    Vec2,
    VectorPath,
    VisualState,
    smooth_rate,
)


def bounce(progress: float) -> float:
    """A caller-defined overshoot curve for the incoming movement segment."""
    q = progress - 1
    return 1 + 2.70158 * q**3 + 1.70158 * q**2


def build() -> Scene:
    motion = Timeline().keyframes(
        StateKeyframe(0.65, StatePatch(position=Vec2(450, 360)), bounce),
        StateKeyframe(1.7, StatePatch(position=Vec2(830, 360), fill=PINK), smooth_rate),
        StateKeyframe(2.4, StatePatch(position=Vec2(640, 360), fill=CYAN), smooth_rate),
    )
    motion.play(Tween(StatePatch(rotation=360)), duration=2.4, at=0)
    motion.wait(0.3).keyframes(StateKeyframe(0.5, StatePatch(opacity=0)))
    tile = PathObject(
        id="tile",
        lifetime=Lifetime(0, 3.2),
        path=VectorPath.rectangle(80, 80).map(lambda point: point - Vec2(40, 40)),
        state=VisualState(position=Vec2(150, 360), fill=CYAN),
        animations=motion.clips,
    )
    return Scene(Document.create()).add(tile)


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
