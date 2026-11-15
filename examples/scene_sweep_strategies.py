"""Fixed sweep strategy experiment; every mode exports ordinary ASS.

uv run python -m examples.scene_sweep_strategies output.ass --strategy bands
Use layers, raster or diffused to inspect explicit compositing/cost tradeoffs.
The small viewport and 10Hz grid are shared experimental settings, not E11's preset.
"""

import argparse
from dataclasses import replace
from pathlib import Path
from typing import Literal

from kara_templater import (
    PINK,
    WHITE,
    Document,
    Lifetime,
    ObjectGroup,
    RasterSettings,
    RectangleClip,
    RectangleFunction,
    Scene,
    SceneBudget,
    SoftSweep,
    TextObject,
    Vec2,
    VisualState,
    rasterize_group,
)

type Strategy = Literal["bands", "layers", "raster", "diffused"]

RESOLUTION = (320, 180)
BUDGET = SceneBudget(
    fps=10, max_events=250_000, max_active=10_000, max_bytes=128 * 1024 * 1024
)
RASTER_SETTINGS = RasterSettings(max_channel_error=0, max_frames=24)


def build(strategy: Strategy = "bands") -> Scene:
    lifetime = Lifetime(0, 2)
    field = SoftSweep(
        left=40,
        right=280,
        start=0.2,
        duration=1.6,
        fill=(WHITE, PINK),
        outline=(WHITE, PINK),
        width=24,
        outline_width=24,
    )
    word = TextObject(
        id="word",
        text="SWEEP",
        font_size=44,
        alignment=5,
        lifetime=lifetime,
        state=VisualState(position=Vec2(160, 90), fill=WHITE, outline=WHITE, border=1),
    )
    glow = replace(
        word.copy(id="glow"),
        layer=-1,
        state=replace(
            word.state, fill=PINK, outline=PINK, border=3, blur=4, opacity=0.6
        ),
    )
    foreground: tuple[TextObject, ...] = (replace(word, material=field),)
    if strategy == "layers":
        # Layer i raises accumulated alpha from i/N to (i+1)/N.
        # Quantized alpha and repeated antialiased coverage remain measurable.
        count = 16
        layers = []
        for index in range(count):
            offset = 12 - 24 * (index + 0.5) / count

            def clip(
                time: float, edge_offset: float = offset
            ) -> tuple[float, float, float, float] | None:
                edge = field.front_at(time) + edge_offset
                return (0, 0, edge, 180) if edge > 0 else None

            layers.append(
                replace(
                    word.copy(id=f"layer:{index}"),
                    layer=index + 1,
                    state=replace(
                        word.state, fill=PINK, outline=PINK, opacity=1 / (count - index)
                    ),
                    clip=RectangleClip(
                        0,
                        0,
                        320,
                        180,
                        deform=RectangleFunction(clip, breakpoints=(0.2, 1.8)),
                    ),
                )
            )
        foreground = (word, *layers)
    group = ObjectGroup(id="sweep", lifetime=lifetime, children=(glow, *foreground))
    if strategy in ("raster", "diffused"):
        return rasterize_group(
            group,
            resolution=RESOLUTION,
            blur_radius=2 if strategy == "diffused" else 0,
            settings=RASTER_SETTINGS,
            budget=BUDGET,
        ).scene
    return Scene(Document.create(width=RESOLUTION[0], height=RESOLUTION[1])).add(group)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--strategy", choices=("bands", "layers", "raster", "diffused"), default="bands"
    )
    args = parser.parse_args()
    result = build(args.strategy).compile(budget=BUDGET)
    result.document.save(args.output)
    print(
        f"{result.event_count} events, {result.peak_active} active, {result.byte_count} bytes"
    )


if __name__ == "__main__":
    main()
