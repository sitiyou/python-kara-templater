"""Singing-relative emphasis and independent glyph exits.

uv run python -m examples.lyric_pulse_drift build/pulse-drift.ass
Use --custom for note-length-dependent emphasis and a curved custom exit.
"""

import argparse
from pathlib import Path

from kara_templater import (
    CYAN,
    PINK,
    Box,
    Document,
    DriftOut,
    Layout,
    Line,
    LyricAnimationContext,
    LyricGradient,
    LyricHighlights,
    LyricRule,
    LyricScene,
    ScalePulse,
    StatePatch,
    Style,
    Track,
    Transform,
    Vec2,
    prepare_tracks,
    smooth_rate,
    smoother_rate,
)


def pulse(timing: LyricAnimationContext) -> ScalePulse:
    """Short notes move less; each repeated singing interval gets its own peak."""
    return ScalePulse(
        peak=1 + 0.06 * smooth_rate(min(1, timing.duration / 0.6)),
        peak_at=0.42,
        rate=smoother_rate,
    )


def build(*, custom: bool = False) -> LyricScene:
    """Compare 250 ms and 2 s notes using the same normalized animation."""
    document = Document.create(
        width=640,
        height=360,
        styles=(Style(fontname="DejaVu Sans", fontsize=48, outline=2, shadow=0),),
    )
    document.records.append(
        Line(
            start_time=1000,
            end_time=4500,
            text=r"{\k25}A{\k25}B{\k100}C{\k200}D",
        )
    )
    exit_motion = (
        Transform(
            offset=lambda p: Vec2(24 * smooth_rate(p), -36 * p * p),
            scale=lambda p: 1 - 0.04 * smooth_rate(p),
            opacity=lambda p: 1 - smooth_rate(p),
        )
        if custom
        else DriftOut(offset=Vec2(24, -36))
    )
    return prepare_tracks(
        document,
        tracks=(
            Track(
                tail=0,
                id="main",
                region=Box(40, 180, 560, 140),
                layout=Layout(alignment="center"),
                effects=(
                    LyricRule(
                        "character", "singing", pulse if custom else ScalePulse(peak=1.06, peak_at=0.42)
                    ),
                    LyricRule(
                        "character",
                        "after_singing",
                        exit_motion,
                        offset=0.14,
                        duration=0.56,
                    ),
                    LyricHighlights.from_singing(
                        StatePatch(fill=CYAN),
                        material=LyricGradient((CYAN, PINK)),
                    ),
                ),
            ),
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--custom", action="store_true")
    args = parser.parse_args()
    result = build(custom=args.custom).compile(native_tweens=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(result.document.dumps(), encoding="utf-8-sig")
    print(f"{result.event_count} events, {result.byte_count} bytes")


if __name__ == "__main__":
    main()
