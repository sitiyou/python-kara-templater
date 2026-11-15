"""Soft fill, outline and independently animated glow, colored before blur.

uv run python -m examples.scene_coverage output.ass
The fixed small viewport makes the explicit pixel-output cost practical.
"""

import argparse
from math import sin, tau
from pathlib import Path

from kara_templater import (
    CYAN,
    PINK,
    WHITE,
    CoverageResult,
    Document,
    Glow,
    GlowFunction,
    Lifetime,
    ObjectGroup,
    RasterSettings,
    SceneBudget,
    SceneTimeline,
    SoftSweep,
    StatePatch,
    TextObject,
    Tween,
    Vec2,
    VisualState,
    compile_coverage,
)

BUDGET = SceneBudget(
    fps=10, max_events=250_000, max_active=10_000, max_bytes=128 * 1024 * 1024
)
RASTER_SETTINGS = RasterSettings(max_channel_error=8, max_frames=100)


def glow(state: VisualState, seconds: float) -> Glow:
    """An ordinary pure function; arbitrary seeks produce the same appearance."""
    return Glow(color=PINK, border=3, blur=3 + sin(tau * seconds / 3), opacity=0.7)


def build() -> CoverageResult:
    lifetime = Lifetime(0, 5)
    sweep = SoftSweep(
        left=45,
        right=275,
        start=1,
        duration=3,
        fill=(WHITE, PINK),
        outline=(CYAN, PINK),
        width=18,
        outline_width=26,
    )
    word = TextObject(
        id="word",
        text="GLOW",
        font_size=68,
        alignment=5,
        lifetime=lifetime,
        state=VisualState(position=Vec2(160, 90), border=2),
        material=sweep,
    )
    fade = (
        SceneTimeline()
        .play(Tween(StatePatch(opacity=1)), duration=0.4)
        .wait(4.2)
        .play(Tween(StatePatch(opacity=0)), duration=0.4)
    )
    group = ObjectGroup(
        id="lyrics",
        lifetime=lifetime,
        children=(word,),
        state=VisualState(opacity=0),
        animations=fade.clips,
    )
    return compile_coverage(
        Document.create(width=320, height=180),
        group,
        glows={word.id: GlowFunction(glow, max_blur=4, max_border=3)},
        glow_materials={
            word.id: SoftSweep(
                left=45, right=275, start=1, duration=3, fill=(CYAN, PINK), width=26
            )
        },
        settings=RASTER_SETTINGS,
        budget=BUDGET,
    )


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
