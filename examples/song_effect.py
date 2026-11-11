"""Use with: kara-templater input.ass output.ass --effect examples/song_effect.py."""

from kara_templater import (
    BLACK,
    Body,
    Color,
    Effect,
    Halo,
    Lyrics,
    ProgressCurve,
    Ruby,
)

CYAN = Color.hex("#33ddff")


class SongEffect(Effect):
    def compose(self):
        yield Lyrics(
            Body(fill=Color(230, 230, 230), stroke=BLACK, stroke_width=2),
            Ruby(stroke_width=2, offset_y=-4, follow="syllable"),
            Halo(color=CYAN, blur=4, width=3, opacity=0.5, clip="sung"),
        )

    def configure(self):
        self.text.sweep(
            fill=CYAN,
            curve=ProgressCurve.two_stage(time_fraction=0.25, progress_fraction=0.4),
            padding=8,
            lead=80,
            tail=100,
        )
        self.syllables.on_singing(pulse=1.1)
        self.text.fade(in_ms=100, out_ms=100)


effect = SongEffect
