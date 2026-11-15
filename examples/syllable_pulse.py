"""Grow during this syllable; shrink during the next, still on this target."""

import argparse
from pathlib import Path

from kara_templater import (
    AnimationContext,
    Body,
    Composition,
    Document,
    LineMatch,
    ScaleTo,
    Timeline,
    Track,
    render_karaoke,
    smooth,
)


class SyllablePulse(Composition):
    def __init__(
        self,
        *,
        peak: float = 1.12,
        last_release: float = 0.2,
    ) -> None:
        super().__init__(extend_display=True)
        self.peak = peak
        self.last_release = last_release

    def compose(self, timeline: Timeline, context: AnimationContext) -> None:
        current = context.syllable
        following = context.next_syllable
        if current.duration > 0:
            timeline.play(ScaleTo(self.peak, rate=smooth), during=current.interval)
        if following is not None and following.duration > 0:
            timeline.play(ScaleTo(1.0, rate=smooth), during=following.interval)
        else:
            timeline.play(
                ScaleTo(1.0, rate=smooth),
                at=current.end,
                duration=self.last_release,
            )


track = Track(source=LineMatch(), body=Body(), animations=(SyllablePulse(),))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = render_karaoke(Document.load(args.input), tracks=(track,))
    result.document.save(args.output)


if __name__ == "__main__":
    main()
