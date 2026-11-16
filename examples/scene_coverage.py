"""Soft fill, outline and independently animated glow, colored before blur.

uv run python -m examples.scene_coverage output.ass
The fixed small viewport makes the explicit pixel-output cost practical.
"""

import argparse
from dataclasses import replace
from math import sin, tau
from pathlib import Path

from kara_templater import (
    CYAN,
    PINK,
    WHITE,
    Coverage,
    Document,
    Glow,
    GlowFunction,
    Lifetime,
    ObjectGroup,
    RasterSettings,
    Scene,
    SceneBudget,
    SceneResult,
    SoftSweep,
    StatePatch,
    TextObject,
    Timeline,
    Tween,
    Vec2,
    VisualState,
)

BUDGET = SceneBudget(
    fps=10, max_events=250_000, max_active=10_000, max_bytes=128 * 1024 * 1024
)
RASTER_SETTINGS = RasterSettings(max_channel_error=8, max_frames=100)


def glow(state: VisualState, seconds: float) -> Glow:
    """An ordinary pure function; arbitrary seeks produce the same appearance."""
    return Glow(color=PINK, border=3, blur=3 + sin(tau * seconds / 3), opacity=0.7)


def build() -> SceneResult:
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
        Timeline()
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
    config = Coverage(
        glows={word.id: GlowFunction(glow, max_blur=4, max_border=3)},
        glow_materials={
            word.id: SoftSweep(
                left=45, right=275, start=1, duration=3, fill=(CYAN, PINK), width=26
            )
        },
        settings=RASTER_SETTINGS,
    )
    return (
        Scene(Document.create(width=320, height=180))
        .add(replace(group, coverage=config))
        .compile(budget=BUDGET)
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = build()
    result.document.save(args.output)
    print(
        f"{len(result.objects[0].sample_times)} samples, {result.event_count} events, "
        f"{result.peak_active} active, {result.byte_count} bytes"
    )


if __name__ == "__main__":
    main()
