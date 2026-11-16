"""Typed object animation: staggered letters, a group and a custom curve.

Run: uv run python -m examples.scene_staggered output.ass
This early E02 example generates standard ASS without any input file.
"""

import argparse
from dataclasses import replace
from math import sin, tau
from pathlib import Path

from kara_templater import (
    CYAN,
    PINK,
    AnimationClip,
    Document,
    Lifetime,
    ObjectGroup,
    PathObject,
    Record,
    Scene,
    StateFunction,
    StatePatch,
    TextObject,
    Timeline,
    Tween,
    Vec2,
    VectorPath,
    VisualState,
    smooth_rate,
)


def bounce(progress: float) -> float:
    """An author-defined easing; no compiler-specific tags needed."""
    p = progress - 1
    return 1 + 2.70158 * p**3 + 1.70158 * p**2


def orbit(state: VisualState, progress: float) -> VisualState:
    return replace(
        state,
        position=state.position + Vec2(480 * progress, 32 * sin(tau * progress)),
        rotation=360 * progress,
    )


def build() -> Scene:
    document = Document(
        [
            "[Script Info]",
            "ScriptType: v4.00+",
            "YCbCr Matrix: None",
            "PlayResX: 1280",
            "PlayResY: 720",
            "ScaledBorderAndShadow: yes",
            "WrapStyle: 2",
        ],
        Record(res_x=1280, res_y=720),
    )
    letters: list[TextObject] = []
    for index, letter in enumerate("Tiny stars"):
        x = index * 59
        timeline = Timeline()
        timeline.play(
            Tween(StatePatch(position=Vec2(x, 0)), bounce),
            Tween(StatePatch(opacity=1)),
            duration=0.65,
            at=index * 0.08,
        )
        timeline.play(
            Tween(StatePatch(position=Vec2(x, -40), opacity=0), smooth_rate),
            duration=0.5,
            at=4 + index * 0.04,
        )
        letters.append(
            TextObject(
                id=f"letter-{index}",
                text=letter,
                font_size=64,
                lifetime=Lifetime(0, 5),
                state=VisualState(position=Vec2(x, 60), opacity=0, fill=CYAN, border=1),
                animations=timeline.clips,
            )
        )
    group = ObjectGroup(
        id="title",
        lifetime=Lifetime(0, 5),
        state=VisualState(position=Vec2(350, 300)),
        children=tuple(letters),
    )
    diamond = PathObject(
        id="orbit",
        lifetime=Lifetime(0.5, 4.5),
        path=VectorPath.polygon(Vec2(0, -9), Vec2(7, 0), Vec2(0, 9), Vec2(-7, 0)),
        state=VisualState(position=Vec2(390, 420), fill=PINK),
        animations=(
            AnimationClip(
                0, 4, StateFunction(orbit, frozenset(("position", "rotation")))
            ),
        ),
    )
    return Scene(document).add(group, diamond)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = build().compile()
    result.document.save(args.output)
    print(
        f"{result.event_count} events, {result.peak_active} active, {result.byte_count} bytes"
    )


if __name__ == "__main__":
    main()
