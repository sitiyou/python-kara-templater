"""Whole-unit glow ramp independent of the body's spatial sweep.

Run: python -m examples.whole_glow /tmp/whole-glow.ass
Or: kara-templater input.ass output.ass --effect examples/whole_glow.py

This recipe handles body text. Ruby is explicitly disabled. Each source unit
ramps across its first-to-last segment, including intervening singing gaps.
"""

import argparse
from dataclasses import dataclass, field, replace
from pathlib import Path

from kara_templater import (
    BLACK,
    Body,
    Color,
    Effect,
    Glow,
    Halo,
    Lyrics,
    SamplingSettings,
)


@dataclass
class WholeGlow(Effect):
    glow: Glow = field(
        default_factory=lambda: Glow(Color(40, 220, 255), blur=24, border=3)
    )
    initial_opacity: float = 0.2
    final_opacity: float = 0.8
    step_ms: int = 40

    def __post_init__(self):
        replace(self.glow, opacity=self.initial_opacity)
        replace(self.glow, opacity=self.final_opacity)
        SamplingSettings(step_ms=self.step_ms)

    def compose(self):
        yield Lyrics(
            Body(fill="#c8c8c8", stroke=BLACK, stroke_width=0, opacity=1),
            Halo(
                id="whole",
                color=self.glow.color,
                width=self.glow.border,
                blur=self.glow.blur,
                opacity=self.initial_opacity,
            ),
        )

    def configure(self):
        self.sampling = SamplingSettings(step_ms=self.step_ms)
        self.text.sweep(fill="#28dcff")
        self.query_one("#whole").on_singing(
            opacity=(self.initial_opacity, self.final_opacity),
            keep=True,
        )


effect = WholeGlow()


def main():
    from examples.staggered_path import scene

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = scene(effect)
    result.document.save(args.output)
    print(f"{result.event_count} events; {len(result.diagnostics)} diagnostics")


if __name__ == "__main__":
    main()
