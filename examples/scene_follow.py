"""World-space followers, delayed history and a custom two-target midpoint.

uv run python -m examples.scene_follow output.ass
"""

import argparse
from dataclasses import replace
from pathlib import Path

from kara_templater import (
    CYAN,
    PINK,
    AnimationClip,
    Contour,
    CubicSegment,
    Document,
    FollowObject,
    Lifetime,
    MoveAlong,
    ObjectGroup,
    PathObject,
    ReferenceFunction,
    Scene,
    StateLookup,
    TextObject,
    Vec2,
    VectorPath,
    VisualState,
)


def midpoint(base: VisualState, time: float, lookup: StateLookup) -> VisualState:
    leader = lookup("leader", time).position
    anchor = lookup("anchor", time).position
    return replace(base, position=leader.lerp(anchor, 0.5))


def build() -> Scene:
    lifetime = Lifetime(0, 5)
    leader = TextObject(
        id="leader",
        text="FOLLOW",
        alignment=5,
        font_size=64,
        lifetime=lifetime,
        state=VisualState(fill=CYAN),
        animations=(
            AnimationClip(
                0.5,
                3.5,
                MoveAlong(
                    Contour(
                        Vec2(),
                        (CubicSegment(Vec2(250, -150), Vec2(500, 150), Vec2(750, 0)),),
                        False,
                    )
                ),
            ),
        ),
    )
    group = ObjectGroup(
        id="moving-parent",
        lifetime=lifetime,
        state=VisualState(position=Vec2(200, 300)),
        children=(leader,),
    )
    caption = TextObject(
        id="caption",
        text="world-space anchor",
        alignment=5,
        font_size=28,
        lifetime=lifetime,
        reference=FollowObject("leader", offset=Vec2(0, 80)),
    )
    trails = tuple(
        PathObject(
            id=f"history:{i}",
            lifetime=lifetime,
            path=VectorPath.circle(9),
            state=VisualState(fill=PINK, opacity=0.7 - i * 0.08),
            reference=FollowObject("leader", offset=Vec2(0, 35), delay=i * 0.12),
        )
        for i in range(1, 6)
    )
    anchor = PathObject(
        id="anchor",
        lifetime=lifetime,
        path=VectorPath.circle(8),
        state=VisualState(position=Vec2(100, 100), fill=PINK),
    )
    center = PathObject(
        id="midpoint",
        lifetime=lifetime,
        path=VectorPath.circle(8),
        state=VisualState(fill=CYAN),
        reference=ReferenceFunction(
            midpoint, ("leader", "anchor"), frozenset(("position",))
        ),
    )
    return Scene(Document.create()).add(*trails, caption, group, anchor, center)


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
