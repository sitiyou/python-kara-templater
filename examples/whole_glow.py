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
    Color,
    DynamicEffect,
    DynamicProperties,
    Glow,
    KaraokeEffect,
    Paint,
    PaintPair,
    RubyPolicy,
    SamplingSettings,
    Segment,
)


@dataclass(frozen=True)
class WholeGlow:
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

    def build(self, target, context):
        plan = KaraokeEffect(
            paints=PaintPair(Paint(Color(200, 200, 200)), Paint(Color(40, 220, 255))),
            ruby=RubyPolicy(enabled=False),
        ).build(target, context)
        order = min((layer.order for layer in plan.layers), default=0) - 1
        seen, timings, glow_layers = set(), {}, []
        for layer in plan.layers:
            # A glyph may appear in many mask regions/time exposures. Emit its
            # unmasked glow exactly once, with the original global window.
            identity = layer.animation_id or layer.source_id
            if identity in seen:
                continue
            seen.add(identity)
            glow_id = identity + "/whole-glow"
            segments = [ref.resolve(target) for ref in layer.origin.sources]
            segments = [s for s in segments if isinstance(s, Segment)]
            if segments:
                timings[glow_id] = (
                    min(s.start_ms for s in segments),
                    max(s.end_ms for s in segments),
                )
            glow_layers.append(
                replace(
                    layer,
                    source_id=glow_id,
                    animation_id=glow_id,
                    component="glow",
                    paint=Paint(glow=self.glow),
                    clips=None,
                    active_window=None,
                    order=order,
                    origin=replace(layer.origin, effect="WholeGlow"),
                )
            )

        def properties(sample):
            if sample.target_id not in seen_glows:
                return DynamicProperties()
            timing = timings.get(sample.target_id)
            progress = 0
            if timing is not None:
                start, end = timing
                progress = (
                    float(sample.time_ms >= end)
                    if start == end
                    else min(1, max(0, (sample.time_ms - start) / (end - start)))
                )
            return DynamicProperties(
                glow_opacity=self.initial_opacity
                + (self.final_opacity - self.initial_opacity) * progress
            )

        seen_glows = {layer.animation_id for layer in glow_layers}
        return replace(
            plan,
            layers=(*glow_layers, *plan.layers),
            dynamic=DynamicEffect(properties, SamplingSettings(step_ms=self.step_ms)),
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
