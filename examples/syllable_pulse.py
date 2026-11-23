"""Grow during this syllable; shrink during the next, on the same target.

The factory records seconds into the common timeline. Layout reserves the whole
returned sequence before binding it; the author does not schedule each glyph.
"""

import argparse
from dataclasses import dataclass
from pathlib import Path

from kara_templater import (
    Document,
    LyricAnimationContext,
    LyricRule,
    StatePatch,
    Timeline,
    Track,
    Tween,
    Vec2,
    prepare_tracks,
    smooth_rate,
)
from kara_templater.geometry import finite
from kara_templater.scene_animation import AnimationSequence, StateAnimation


@dataclass(frozen=True)
class SyllablePulse:
    peak: float = 1.12
    last_release: float = 0.2

    def __post_init__(self) -> None:
        finite(self.peak, self.last_release)
        if self.peak <= 0 or self.last_release <= 0:
            raise ValueError("pulse peak and release must be positive")

    def __call__(self, timing: LyricAnimationContext) -> StateAnimation:
        if not timing.target.singing:
            return Tween(StatePatch(scale=Vec2(1, 1)))
        targets = timing.line.query("syllable")
        index = targets.index(timing.target)
        current = timing.target.singing[0]
        following = targets[index + 1] if index + 1 < len(targets) else None
        next_span = (
            following.singing[0]
            if following is not None and following.singing
            else None
        )
        timeline = Timeline()
        if current.end > current.start:
            timeline.play(
                Tween(StatePatch(scale=Vec2(self.peak, self.peak)), smooth_rate),
                duration=current.end - current.start,
            )
        if next_span is not None and next_span.end > next_span.start:
            at, duration = (
                next_span.start - current.start,
                next_span.end - next_span.start,
            )
        else:
            at, duration = current.end - current.start, self.last_release
        timeline.play(
            Tween(StatePatch(scale=Vec2(1, 1)), smooth_rate), at=at, duration=duration
        )
        result: AnimationSequence = timeline.animation
        return result


track = Track(
    id="lyrics",
    effects=(LyricRule("syllable", "singing", SyllablePulse()),),
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    scene = prepare_tracks(Document.load(args.input), tracks=(track,))
    scene.ass.compile().document.save(args.output)


if __name__ == "__main__":
    main()
