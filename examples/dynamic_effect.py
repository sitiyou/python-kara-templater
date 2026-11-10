"""CLI recipe: --effect examples/dynamic_effect.py --max-events 100000.

Property values are held for 40 ms; normal sweep and pulse remain interpolated.
"""

from math import sin, tau

from kara_templater import (
    Color,
    DynamicEffect,
    DynamicProperties,
    Glow,
    KaraokeEffect,
    Paint,
    PaintPair,
    SamplingSettings,
)


def properties(context):
    phase = context.noise("phase", animated=False) * tau
    wave = sin(context.time_ms / 1000 * tau + phase)
    return DynamicProperties(offset_y=4 * wave, glow_blur=10 + 8 * wave)


effect = KaraokeEffect(
    paints=PaintPair(
        before=Paint(Color(180, 180, 180), glow=Glow(blur=10)),
        after=Paint(Color(255, 160, 80), glow=Glow(blur=10)),
    ),
    dynamic=DynamicEffect(
        properties, SamplingSettings(step_ms=40), seed=42, max_glow_blur=18
    ),
)
