"""Track-configured ruby/sweep/glow, then custom motion and vector decoration.

uv run python -m examples.scene_coverage_tracks output.ass
"""

import argparse
from dataclasses import replace
from math import sin, tau
from pathlib import Path

from kara_templater import (
    CYAN,
    PINK,
    WHITE,
    Animate,
    AnimationClip,
    Blur,
    Body,
    CoverageResult,
    Display,
    Document,
    Line,
    LineMatch,
    On,
    Overlay,
    PaintStyle,
    PathObject,
    RasterSettings,
    Ruby,
    SceneBudget,
    SingleLine,
    StateFunction,
    Style,
    TextStyle,
    Track,
    Vec2,
    VectorPath,
    VisualState,
    prepare_track_coverage,
)

BUDGET = SceneBudget(
    fps=10, max_events=200_000, max_active=5000, max_bytes=64 * 1024 * 1024
)
RASTER_SETTINGS = RasterSettings(max_channel_error=8, max_frames=100)


def drift(state: VisualState, progress: float) -> VisualState:
    return replace(state, position=state.position + Vec2(0, 5 * sin(tau * progress)))


def build() -> CoverageResult:
    document = Document.create(
        width=240,
        height=135,
        styles=(Style(fontname="DejaVu Sans", fontsize=40, shadow=0, align=5),),
    )
    document.records.append(
        Line(text=r"{\k100}Fly|fly{\k100} on|on", start_time=500, end_time=3500)
    )
    track = Track(
        source=LineMatch(),
        body=Body(
            style=TextStyle(fill=WHITE, blur=Blur(color=CYAN, radius=2, width=2))
        ),
        ruby=Ruby(
            style=TextStyle(
                fill=WHITE, stroke_width=0, blur=Blur(color=CYAN, radius=1, width=1)
            )
        ),
        overlay=Overlay(style=PaintStyle(fill=PINK)),
        layout=SingleLine(position=(50, 64)),
        animations=(
            On(
                Display.Start,
                Animate(blur_color=(CYAN, PINK), duration=2500, keep=True),
            ),
        ),
    )
    prepared = prepare_track_coverage(
        document, tracks=(track,), max_glow_blur=2, max_glow_border=2
    )
    root = prepared.group
    underline = PathObject(
        id="underline",
        lifetime=root.lifetime,
        path=VectorPath.rectangle(140, 2),
        state=VisualState(position=Vec2(50, 112), fill=PINK),
    )
    prepared = replace(
        prepared,
        group=replace(
            root,
            children=(*root.children, underline),
            animations=(
                AnimationClip(
                    0,
                    root.lifetime.end - root.lifetime.start,
                    StateFunction(drift, frozenset(("position",))),
                ),
            ),
        ),
    )
    return prepared.compile(settings=RASTER_SETTINGS, budget=BUDGET)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = build()
    result.document.save(args.output)
    print(
        f"{len(result.sample_times)} samples, {result.output.event_count} events, "
        f"{result.output.peak_active} active, {result.output.byte_count} bytes"
    )


if __name__ == "__main__":
    main()
