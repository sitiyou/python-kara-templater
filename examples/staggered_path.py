"""Sweep-triggered per-character arcs using only public APIs.

Run: python -m examples.staggered_path /tmp/staggered.ass
Or: kara-templater input.ass output.ass --effect examples/staggered_path.py
"""

import argparse
from dataclasses import dataclass
from math import pi, sin
from pathlib import Path

from kara_templater import (
    BLACK,
    Body,
    DisplayWindow,
    Document,
    Effect,
    KaraokeItem,
    KaraokeLine,
    Lyrics,
    SamplingSettings,
    Segment,
    Style,
    TextUnit,
    render_karaoke,
)
from kara_templater.ass import EVENT_FORMAT, STYLE_FORMAT


@dataclass
class ArcWave(Effect):
    height: float = 24
    width: float = 8
    duration_ms: int = 400
    step_ms: int = 40

    def compose(self):
        yield Lyrics(Body(fill="#c8c8c8", stroke=BLACK, stroke_width=0, opacity=1))

    def configure(self):
        self.sampling = SamplingSettings(step_ms=self.step_ms)
        self.text.sweep(fill="#28dcff")
        self.characters.on_highlight(
            duration_ms=self.duration_ms,
            offset_x=lambda p: self.width * sin(2 * pi * p),
            offset_y=lambda p: -self.height * sin(pi * p),
        )


effect = ArcWave()


def scene(recipe=effect):
    style = Style(fontname="DejaVu Sans", fontsize=64, align=5)
    document = Document.parse(
        "[Script Info]\nPlayResX: 640\nPlayResY: 480\n"
        "[V4+ Styles]\nFormat: "
        + STYLE_FORMAT
        + "\n"
        + style.serialize()
        + "\n[Events]\nFormat: "
        + EVENT_FORMAT
        + "\n"
    )
    target = KaraokeItem(
        "arc",
        KaraokeLine((TextUnit("Karaoke", (Segment(1000, 2000),)),)),
        "Default",
        DisplayWindow(500, 3000),
    )
    return render_karaoke(document, (target,), effect=recipe)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = scene()
    result.document.save(args.output)
    print(f"{result.event_count} events; {len(result.diagnostics)} diagnostics")


if __name__ == "__main__":
    main()
