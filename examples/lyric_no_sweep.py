"""Mark note attacks with a geometric cue and recolor whole glyphs at release."""

import argparse
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path

from kara_templater import (
    Box,
    Color,
    Document,
    Layout,
    Lifetime,
    Line,
    LyricHighlights,
    LyricLine,
    LyricRule,
    PathObject,
    ScalePulse,
    Scene,
    SceneEvaluator,
    StateKeyframe,
    StatePatch,
    Style,
    Timeline,
    Track,
    Vec2,
    VectorPath,
    VisualState,
    prepare_tracks,
    smooth_rate,
)

FPS = 30
WAITING = Color.hex("#EFEDE3")
COMPLETED = Color.hex("#F4BB73")
EDGE = Color.hex("#192027")
MARKER = Color.hex("#FFC67F")


@dataclass(frozen=True)
class Phrase:
    """Original fixture with one centisecond duration and pitch per glyph."""

    text: str
    start: int
    durations: tuple[int, ...]
    pitches: tuple[int, ...]

    def line(self) -> Line:
        text = "".join(
            rf"{{\k{duration}}}{glyph}"
            for glyph, duration in zip(self.text, self.durations, strict=True)
        )
        return Line(
            start_time=self.start * 10,
            end_time=(self.start + sum(self.durations)) * 10,
            text=text,
        )


PHRASES = (
    Phrase(
        "晚风把路灯点亮", 85, (34, 27, 27, 32, 35, 29, 78), (57, 60, 62, 64, 62, 60, 57)
    ),
    Phrase(
        "我把微光带回家",
        393,
        (30, 29, 32, 34, 32, 33, 92),
        (60, 62, 65, 64, 62, 60, 57),
    ),
)


def _marker(line: LyricLine, evaluator: SceneEvaluator) -> PathObject:
    # The cue and the pulse use the same measured syllable clocks.
    notes = [target for target in line.query("syllable") if target.singing]
    first = notes[0].singing[0].start
    last = notes[-1].singing[-1].end
    top = line.state.position.y + line.layout.body.bounds.top - 31
    stops = [
        (
            note.singing[0].start - first,
            Vec2(
                evaluator.at(note.node_id, note.singing[0].start)
                .transform.apply(note.center)
                .x,
                top,
            ),
        )
        for note in notes
    ]
    keys: list[StateKeyframe] = []
    for (previous_time, previous), (onset, target) in pairwise(stops):
        travel = min(0.12, (onset - previous_time) * 0.45)
        peak = previous.lerp(target, 0.52) + Vec2(0, -13)
        keys.extend(
            (
                StateKeyframe(onset - travel, StatePatch(position=previous)),
                StateKeyframe(
                    onset - travel * 0.48, StatePatch(position=peak), smooth_rate
                ),
                StateKeyframe(onset, StatePatch(position=target), smooth_rate),
            )
        )
    diamond = VectorPath.polygon(Vec2(-10, 0), Vec2(0, -8), Vec2(10, 0), Vec2(0, 8))
    return PathObject(
        id=f"{line.id}/note-marker",
        path=diamond,
        lifetime=Lifetime(first, last),
        layer=2,
        state=VisualState(position=stops[0][1], fill=MARKER, outline=EDGE, border=1.6),
        animations=Timeline().keyframes(*keys).clips if keys else (),
    )


def build() -> Scene:
    """Keep the baseline clear with a fixed reading row and a timed note cue."""
    canvas = Document.create(
        width=1920,
        height=1080,
        styles=(
            Style(
                fontname="Sarasa UI SC", fontsize=98, spacing=13, outline=2.8, shadow=0
            ),
        ),
    )
    canvas.records.extend(phrase.line() for phrase in PHRASES)
    scene = prepare_tracks(
        canvas,
        tracks=(
            Track(
                id="lead",
                layout=Layout(alignment="center"),
                region=Box(240, 763, 1440, 226),
                preview=0.35,
                tail=0.22,
                effects=(
                    LyricHighlights.from_singing(
                        StatePatch(fill=COMPLETED, outline=EDGE),
                        wipe=False,
                        base_paint=StatePatch(fill=WAITING, outline=EDGE),
                    ),
                    LyricRule(
                        "syllable", "singing", ScalePulse(peak=1.13, peak_at=0.24)
                    ),
                ),
            ),
        ),
    )
    evaluator = scene.evaluator()
    lines = tuple(line for line in scene.objects if isinstance(line, LyricLine))
    return scene.add(*(_marker(line, evaluator) for line in lines))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    build().export(args.output, fps=FPS)
