"""Built-in menu choices remain typed and compose with custom lyric effects."""

from typing import assert_type

from kara_templater import (
    Color,
    KaraokeEffects,
    LyricGradient,
    LyricLine,
    Track,
)


def decorate(line: LyricLine) -> LyricLine:
    result = KaraokeEffects(
        entry="assemble_in",
        exit="snow",
        highlight="zoom_pulse_scanline",
        decoration="twinkle_classic",
        material=LyricGradient((Color(0, 200, 255), Color(255, 100, 190))),
    )(line)
    assert_type(result, LyricLine)
    return result


track = Track(id="main", effects=(KaraokeEffects(entry="petal"),))
