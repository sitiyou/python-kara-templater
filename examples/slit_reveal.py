"""Reveal timed lyrics through invisible, fixed openings on a dark background."""

import argparse
from dataclasses import replace
from pathlib import Path

from kara_templater import (
    Color,
    Document,
    Layout,
    Lifetime,
    Line,
    LyricHighlights,
    LyricLine,
    RectangleClip,
    Scene,
    StateKeyframe,
    StatePatch,
    Style,
    TextObject,
    Timeline,
    Track,
    Vec2,
    VisualState,
    outline_text,
    path_bounds,
    prepare_tracks,
)

FPS = 30
UNSUNG = Color.hex("#EDEBE6")
SUNG = Color.hex("#FFD5A0")
DISPLACEMENT = (1.0, 0.573, 0.347, 0.213, 0.127, 0.067, 0.033, 0.013, 0.0)


def _entrance(
    text: TextObject, state: VisualState, start: float, end: float
) -> TextObject:
    path = outline_text(text).path
    if path is None:
        raise ValueError(f"missing outline for {text.id}")
    ink = path_bounds(path.map(state.transform.apply))
    padding = 9
    distance = ink.width + 2 * padding
    return replace(
        text,
        id=f"{text.id}/entrance",
        lifetime=Lifetime(start, end),
        clock_start=None,
        state=replace(state, position=state.position + Vec2(distance, 0)),
        clip=RectangleClip(
            ink.left - padding,
            ink.top - padding,
            ink.right + padding,
            ink.top + ink.height + padding,
        ),
        animations=Timeline()
        .keyframes(
            *(
                StateKeyframe(
                    frame / FPS,
                    StatePatch(position=state.position + Vec2(distance * remaining, 0)),
                )
                for frame, remaining in enumerate(DISPLACEMENT[1:], start=1)
            )
        )
        .clips,
    )


def build() -> Scene:
    """Build lettering that reveals directly over the footage."""
    document = Document.create(
        width=1920,
        height=1080,
        styles=(
            Style(
                fontname="Sarasa UI J", fontsize=122, spacing=44, outline=0, shadow=0
            ),
        ),
    )
    document.records.append(
        Line(start_time=1000, end_time=3100, text=r"{\k50}春{\k35}が{\k55}来{\k70}た")
    )
    scene = prepare_tracks(
        document,
        tracks=(
            Track(
                id="lead",
                layout=Layout(position=Vec2(675, 690)),
                preview=0,
                effects=(
                    LyricHighlights.from_singing(
                        StatePatch(fill=SUNG),
                        base_paint=StatePatch(fill=UNSUNG),
                    ),
                ),
            ),
        ),
    )
    line = next(node for node in scene.objects if isinstance(node, LyricLine))
    evaluator = scene.evaluator()
    end = line.lifetime.start
    characters = line.layout.body.characters
    for offset, cell in enumerate(reversed(characters)):
        glyph = cell.object
        scene.add(
            _entrance(glyph, evaluator.at(glyph.id, end), (10 + offset) / FPS, end)
        )
    return scene


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    build().export(args.output, fps=FPS)
