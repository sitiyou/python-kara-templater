"""Public expression arithmetic keeps length and time contracts distinct."""

from typing import assert_type

from kara_templater import (
    Animation,
    Canvas,
    FadeIn,
    Glyph,
    KaraokeEffects,
    LengthExpr,
    LyricRule,
    Note,
    TimeExpr,
)

edge = assert_type((Glyph.font_size / 6 + 1).clamp(2, 16), LengthExpr)
band = assert_type(Canvas.height / 90, LengthExpr)
KaraokeEffects(singing="scanline", hook_feather=edge, scanline_width=band)
attack = assert_type(0.5 * Note.duration, TimeExpr)
LyricRule("character", "singing", FadeIn(), duration=attack, offset=Animation.duration / 3)
