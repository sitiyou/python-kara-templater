"""Layered lyric glow and syllable emphasis on a fixed K1/K2/LEAD input.

python -m examples.layered_glow tests/fixtures/layered_glow.ass output.ass
The direct script reframes this fixture at 1920x1080. The exported tracks also
work with the CLI; scene_lyrics demonstrates fully editable Scene objects.
"""

import argparse
from pathlib import Path

from kara_templater import (
    BLACK,
    WHITE,
    Blur,
    Body,
    Color,
    Document,
    FadeInAnimation,
    FadeOutAnimation,
    LineMatch,
    OutputSettings,
    Overlay,
    PaintStyle,
    ProgressCurve,
    Ruby,
    SceneResult,
    SingingPulseAnimation,
    Sweep,
    TextStyle,
    Track,
    prepare_tracks,
)

BASE_GLOW = Color.hex("#9e6d64")
SUNG_GLOW = Color.hex("#67e5ff")
SUNG_FILL = Color.hex("#01829d")
SUNG = PaintStyle(fill=SUNG_FILL, stroke=WHITE, blur=Blur(color=SUNG_GLOW))


def glow_body() -> Body:
    return Body(
        style=TextStyle(
            fill=WHITE,
            stroke=BLACK,
            stroke_width=5,
            blur=Blur(color=BASE_GLOW, radius=10, width=10, opacity=0.8),
        )
    )


def glow_ruby() -> Ruby:
    return Ruby(
        style=TextStyle(
            fill=WHITE,
            stroke=BLACK,
            stroke_width=3,
            blur=Blur(color=BASE_GLOW, radius=10, width=6, opacity=0.8),
        ),
        offset_y=10,
        follow="syllable",
    )


# Share immutable colors and construct fresh text components for each Track.
# Omit layout to retain source placement; see layered_glow_classes for subclasses.
tracks = (
    *(
        Track(
            source=LineMatch(style=name),
            body=glow_body(),
            ruby=glow_ruby(),
            overlay=Overlay(
                style=SUNG,
                reveal=Sweep(
                    progress_curve=ProgressCurve.two_stage(
                        time_fraction=3 / 17,
                        progress_fraction=0.3,
                    )
                ),
            ),
            animations=(
                FadeInAnimation(duration=800),
                FadeOutAnimation(duration=200),
                SingingPulseAnimation(peak=1.1, attack=80, release=160),
            ),
        )
        for name in ("K1", "K2")
    ),
    Track(
        source=LineMatch(style="LEAD"),
        body=glow_body(),
        overlay=Overlay(style=SUNG),
        animations=(FadeInAnimation(duration=800), FadeOutAnimation(duration=200)),
    ),
)


def apply(input_path: str | Path, output_path: str | Path) -> SceneResult:
    source = Document.load(input_path)
    document = Document.create(
        width=1920, height=1080, styles=tuple(source.styles.values())
    )
    # This fixture uses dialogue only; template/code comments are not executed.
    document.records.extend(line for line in source.lines if not line.comment)
    # Keep source font families and use fixed presentation coordinates.
    for name, style in document.styles.items():
        style.fontsize, style.spacing, style.shadow = 96, 0, 0
        style.margin_l = style.margin_r = 64
        style.align, style.margin_v = {"K1": (1, 240), "K2": (3, 48), "LEAD": (1, 432)}[
            name
        ]

    result = prepare_tracks(
        document,
        tracks=tracks,
        owner="layered-glow",
        settings=OutputSettings(resolution=(1920, 1080), max_events=1_000_000),
        mode="native",
    ).compile()
    result.document.save(output_path)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = apply(args.input, args.output)
    print(f"{result.event_count} events, {len(result.diagnostics)} diagnostics")


if __name__ == "__main__":
    main()
