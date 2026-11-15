"""E08: explicitly ordered writing strokes and a pen following the same path.

uv run python -m examples.scene_writing output.ass
"""

import argparse
from dataclasses import replace
from pathlib import Path

from kara_templater import (
    CYAN,
    PINK,
    Contour,
    CubicSegment,
    Document,
    Lifetime,
    LineSegment,
    ObjectGroup,
    PathObject,
    Scene,
    SceneTimeline,
    StateFunction,
    Vec2,
    VectorPath,
    VisualState,
    WritePath,
    WritingStroke,
)


def build() -> Scene:
    writing = WritePath(
        (
            WritingStroke(
                Contour(Vec2(0, 170), (LineSegment(Vec2(65, 0)),), False), 0.3, 0.9
            ),
            WritingStroke(
                Contour(Vec2(65, 0), (LineSegment(Vec2(130, 170)),), False), 1.35, 0.9
            ),
            WritingStroke(
                Contour(Vec2(27, 100), (LineSegment(Vec2(103, 100)),), False), 2.4, 0.5
            ),
            WritingStroke(
                Contour(
                    Vec2(190, 120),
                    (
                        CubicSegment(Vec2(260, 200), Vec2(330, -30), Vec2(235, 10)),
                        CubicSegment(Vec2(170, 40), Vec2(220, 190), Vec2(330, 130)),
                    ),
                    False,
                ),
                3.05,
                1.45,
            ),
        ),
        width=6,
        tolerance=0.2,
    )
    lifetime = Lifetime(0, 5)
    ink = PathObject(
        id="ink",
        path=writing.full_path,
        deform=writing,
        lifetime=lifetime,
        state=VisualState(fill=CYAN),
    )

    def pen_state(state: VisualState, progress: float) -> VisualState:
        time = progress * lifetime.end
        return replace(
            state, position=writing.tip(time), opacity=float(writing.pen_down(time))
        )

    pen_motion = SceneTimeline().play(
        StateFunction(pen_state, frozenset(("position", "opacity"))),
        duration=lifetime.end,
        breakpoints=writing.breakpoints,
    )
    pen = PathObject(
        id="pen",
        path=VectorPath.circle(7),
        lifetime=lifetime,
        state=VisualState(fill=PINK),
        layer=1,
        animations=pen_motion.clips,
    )
    return Scene(Document.create()).add(
        ObjectGroup(
            id="handwriting",
            lifetime=lifetime,
            state=VisualState(position=Vec2(470, 250)),
            children=(ink, pen),
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
