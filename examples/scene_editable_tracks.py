"""Style lyrics with Track, then extend their editable group with custom motion.

uv run python -m examples.scene_editable_tracks output.ass
"""

import argparse
from dataclasses import replace
from math import sin, tau
from pathlib import Path

from kara_templater import (
    CYAN,
    PINK,
    WHITE,
    AnimationClip,
    Blur,
    Body,
    Document,
    Line,
    LineMatch,
    ObjectGroup,
    Overlay,
    PaintStyle,
    PathObject,
    Ruby,
    Scene,
    SingingPulseAnimation,
    SingleLine,
    StateFunction,
    Style,
    TextStyle,
    Track,
    Vec2,
    VectorPath,
    VisualState,
    prepare_track_scene,
)


def float_line(base: VisualState, progress: float) -> VisualState:
    return replace(base, position=base.position + Vec2(0, 18 * sin(tau * progress)))


def build() -> Scene:
    document = Document.create(
        styles=(Style(fontname="DejaVu Sans", fontsize=76, align=5, shadow=0),)
    )
    document.records.append(
        Line(
            text=r"{\k100}Make |make{\k100}it |it{\k100}move|move",
            start_time=500,
            end_time=5500,
        )
    )
    track = Track(
        source=LineMatch(),
        body=Body(
            style=TextStyle(fill=WHITE, blur=Blur(color=PINK, radius=4, width=4))
        ),
        ruby=Ruby(style=TextStyle(fill=WHITE, stroke_width=0)),
        overlay=Overlay(style=PaintStyle(fill=CYAN)),
        layout=SingleLine(position=(410, 330)),
        animations=(SingingPulseAnimation(peak=1.1),),
    )
    prepared = prepare_track_scene(document, tracks=(track,))
    scene = prepared.scene
    group = scene.objects[0]
    assert isinstance(group, ObjectGroup)
    underline = PathObject(
        id="underline",
        lifetime=group.lifetime,
        path=VectorPath.rectangle(460, 3),
        state=VisualState(position=Vec2(410, 430), fill=PINK),
    )
    scene.objects[0] = replace(
        group,
        children=(*group.children, underline),
        animations=(
            AnimationClip(
                0,
                group.lifetime.end - group.lifetime.start,
                StateFunction(float_line, frozenset(("position",))),
            ),
        ),
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
