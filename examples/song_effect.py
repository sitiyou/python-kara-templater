"""Use with: kara-templater input.ass output.ass --effect examples/song_effect.py."""

from kara_templater import (
    Color,
    EdgeSweep,
    Fade,
    Glow,
    KaraokeEffect,
    Paint,
    PaintPair,
    ProgressCurve,
    Pulse,
    RubyPolicy,
    Sweep,
)

CYAN = Color.hex("#33ddff")

effect = KaraokeEffect(
    paints=PaintPair(
        before=Paint(Color(230, 230, 230), border=2),
        after=Paint(CYAN, border=2, glow=Glow(CYAN, blur=4, border=3, opacity=0.5)),
    ),
    sweep=Sweep(
        progress_curve=ProgressCurve.two_stage(
            time_fraction=0.25, progress_fraction=0.4
        ),
        edges=EdgeSweep(padding_px=8, lead_ms=80, tail_ms=100),
    ),
    pulses=(Pulse.whole_syllable(),),
    ruby=RubyPolicy(offset_y=-4, follow="syllable"),
    fade=Fade(in_ms=100, out_ms=100),
)
