"""Inline volume bars and a separate row of lamps on the same singing clock."""

import sys
from pathlib import Path

from kara_templater import (
    Color,
    CueMarker,
    CuePreset,
    Document,
    Glow,
    KaraokeEffects,
    KaraokeRows,
    Line,
    LyricScene,
    SignalCue,
    Style,
    Track,
    Vec2,
    VolumeCue,
    prepare_tracks,
)


def build() -> LyricScene:
    styles = tuple(
        Style(
            name=name,
            fontname="DejaVu Sans",
            fontsize=size,
            bold=True,
            outline=2,
            shadow=0,
        )
        for name, size in (("Main", 48), ("Harmony", 31))
    )
    doc = Document.create(width=640, height=360, styles=styles)
    for style, word, placement in (
        ("Main", "Into the light", "inline"),
        ("Harmony", "Sing with me", "independent"),
    ):
        marker = CueMarker("intro", "count", placement=placement)
        doc.records.append(
            Line(
                style=style,
                start_time=3000,
                end_time=4900,
                text=marker.markup() + r"{\k190}" + word,
            )
        )
    # Both types fill the same three-second window in this side-by-side demo.
    return prepare_tracks(
        doc,
        tracks=(
            Track(
                id="main",
                source=lambda s: s.style == "Main",
                layout=KaraokeRows(rows=1),
                cues={
                    "count": CuePreset(
                        factory=VolumeCue(count=3, height=30, border=1.5),
                        lead=3,
                        duration=3,
                        gap=5,
                    )
                },
                effects=(KaraokeEffects(
                    singing="none",
                    base_glow=Glow(color=Color.hex("#9675BD"), border=5),
                    glow=Glow(color=Color.hex("#FFCB86"), border=5),
                ),),
            ),
            Track(
                id="harmony",
                source=lambda s: s.style == "Harmony",
                layout=KaraokeRows(rows=1, anchor="top"),
                cues={
                    "count": CuePreset(
                        factory=SignalCue(
                            shape="star", size=18, border=1, slide=Vec2(0, -5)
                        ),
                        position=Vec2(260, 80),
                        lead=3,
                        duration=3,
                    )
                },
                effects=(KaraokeEffects(
                    singing="none", sung=Color.hex("#23CEAE"),
                    glow=Glow(color=Color.hex("#436C9C"), border=5),
                ),),
            ),
        ),
    )


if __name__ == "__main__":
    build().compile(native_tweens=True).document.save(Path(sys.argv[1]))
