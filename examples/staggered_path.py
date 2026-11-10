"""Sweep-triggered per-character arcs using only public APIs.

Run: python -m examples.staggered_path /tmp/staggered.ass
Or: kara-templater input.ass output.ass --effect examples/staggered_path.py
"""

import argparse
from dataclasses import dataclass, replace
from math import pi, sin
from pathlib import Path

from kara_templater import (
    Color,
    DisplayWindow,
    Document,
    DynamicEffect,
    DynamicProperties,
    KaraokeEffect,
    KaraokeItem,
    KaraokeLine,
    Paint,
    PaintPair,
    Pulse,
    RubyPolicy,
    SamplingSettings,
    Segment,
    Style,
    TextUnit,
    layout_characters,
    plan_pulses,
    render_karaoke,
    tracks_from_layout,
)
from kara_templater.ass import EVENT_FORMAT, STYLE_FORMAT


@dataclass(frozen=True)
class ArcWave:
    height: float = 24
    width: float = 8
    duration_ms: int = 400
    step_ms: int = 40

    def build(self, target, context):
        characters = layout_characters(context.layout, style=context.style)
        tracks = tracks_from_layout(context.layout)
        # Reuse threshold arrival/round/conflict rules. These scale=1 records
        # supply scheduling only; the output recipe emits no scale animation.
        schedule = plan_pulses(
            (Pulse.each_char(scale=1, duration_ms=self.duration_ms),),
            layout=context.layout,
            characters=tuple(c.target for c in characters),
            tracks=tracks,
            window=target.window,
        )
        timings = {}
        for animation in schedule.animations:
            timings.setdefault(f"{target.id}/{animation.target_id}", []).append(
                (animation.start_ms, animation.end_ms)
            )

        def properties(sample):
            for start, end in timings.get(sample.target_id, ()):
                if start <= sample.time_ms < end:
                    progress = (sample.time_ms - start) / (end - start)
                    return DynamicProperties(
                        offset_x=self.width * sin(2 * pi * progress),
                        offset_y=-self.height * sin(pi * progress),
                    )
            return DynamicProperties()

        plan = KaraokeEffect(
            paints=PaintPair(Paint(Color(200, 200, 200)), Paint(Color(40, 220, 255))),
            tracks=tracks,
            ruby=RubyPolicy(enabled=False),
            dynamic=DynamicEffect(properties, SamplingSettings(step_ms=self.step_ms)),
        ).build(target, context)
        return replace(plan, diagnostics=(*schedule.diagnostics, *plan.diagnostics))


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
