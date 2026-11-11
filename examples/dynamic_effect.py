"""CLI effect: --effect examples/dynamic_effect.py --max-events 100000.

Contextual properties share deterministic source noise across text and Halo.
Values are held for 40 ms; ordinary sweep remains interpolated.
"""

from math import sin, tau

from kara_templater import (
    BLACK,
    WHITE,
    Body,
    Color,
    Contextual,
    Effect,
    Halo,
    Lyrics,
    Ruby,
    SamplingSettings,
    display,
)


def wave(context):
    phase = context.noise("phase", animated=False, scope="source") * tau
    return sin(context.time_ms / 1000 * tau + phase)


class DynamicGlow(Effect):
    def compose(self):
        yield Lyrics(
            Body(fill=Color(180, 180, 180), stroke=BLACK, stroke_width=0),
            Ruby(stroke_width=0),
            Halo(color=WHITE, blur=10, max_blur=18),
        )

    def configure(self):
        self.sampling = SamplingSettings(step_ms=40)
        self.text.sweep(fill=Color(255, 160, 80))
        for selection in (self.characters, self.rubies):
            selection.animate(
                offset_y=Contextual(lambda ctx: 4 * wave(ctx), seed=42),
                during=(display.start, display.end),
            )
        self.query_one("halo").animate(
            blur=Contextual(lambda ctx: 10 + 8 * wave(ctx), seed=42),
            during=(display.start, display.end),
        )


effect = DynamicGlow
