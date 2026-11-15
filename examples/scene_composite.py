"""Explicit color composition → group blur → group alpha, baked into standard ASS.

uv run python -m examples.scene_composite output.ass
The small fixed viewport and declared palette error keep this costly mode bounded.
"""

import argparse
from pathlib import Path

from kara_templater import (
    CYAN,
    PINK,
    Lifetime,
    ObjectGroup,
    RasterSettings,
    Scene,
    SceneBudget,
    SceneTimeline,
    StatePatch,
    TextObject,
    Tween,
    Vec2,
    VisualState,
    rasterize_group,
)

BUDGET = SceneBudget(
    fps=10, max_events=250_000, max_active=10_000, max_bytes=128 * 1024 * 1024
)

RASTER_SETTINGS = RasterSettings(max_channel_error=8, max_frames=100)


def build() -> Scene:
    lifetime = Lifetime(0, 5.5)
    fade = (
        SceneTimeline()
        .wait(0.5)
        .play(Tween(StatePatch(opacity=0.3)), duration=1)
        .wait(2)
        .play(Tween(StatePatch(opacity=1)), duration=1)
    )
    word = ObjectGroup(
        id="colored-word",
        lifetime=lifetime,
        animations=fade.clips,
        children=tuple(
            TextObject(
                id=f"letter:{index}",
                text=letter,
                font_size=72,
                alignment=5,
                lifetime=lifetime,
                state=VisualState(
                    position=Vec2(90 + index * 42, 85),
                    fill=CYAN if index % 2 == 0 else PINK,
                ),
            )
            for index, letter in enumerate("FLOW")
        ),
    )
    baked = rasterize_group(
        word,
        resolution=(320, 180),
        blur_radius=1.5,
        settings=RASTER_SETTINGS,
        budget=BUDGET,
    )
    return baked.scene.add(
        TextObject(
            id="caption",
            text="COMPOSE  /  BLUR  /  FADE",
            lifetime=lifetime,
            font_size=12,
            alignment=5,
            layer=1,
            state=VisualState(position=Vec2(160, 145)),
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    output = parser.parse_args().output
    result = build().compile(budget=BUDGET)
    result.document.save(output)
    print(
        f"{result.event_count} events, {result.peak_active} active, {result.byte_count} bytes"
    )


if __name__ == "__main__":
    main()
