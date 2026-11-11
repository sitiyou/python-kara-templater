"""Combination fixture: parallel sweeps, two halos, ruby and scale curves."""

from dataclasses import dataclass

from kara_templater import (
    BLACK,
    CYAN,
    ORANGE,
    WHITE,
    Body,
    Effect,
    Halo,
    HighlightTrack,
    Keyframe,
    Keyframes,
    Lyrics,
    Region,
    Ruby,
    SamplingSettings,
    SingingPass,
    Transition,
    there_and_back,
)


@dataclass
class ComposedGlow(Effect):
    target: str = "group"
    follow_ruby: bool = True
    sung_clip: bool = False
    curve: str = "native"
    translate: bool = False
    additive_offsets: bool = False

    def compose(self):
        yield Lyrics(
            Body(fill=WHITE, stroke=BLACK, stroke_width=2),
            Ruby(follow="syllable" if self.follow_ruby else "none", offset_y=4),
            Halo(color=ORANGE, width=8, ruby_width=4, blur=8, opacity=0.3),
            Halo(
                id="active",
                color=CYAN,
                width=4,
                ruby_width=2,
                blur=6,
                opacity=0.4,
                clip="sung" if self.sung_clip else "none",
            ),
        )

    def configure(self):
        self.sampling = SamplingSettings(step_ms=10)
        self.text.sweep(fill=CYAN, tracks=self.tracks)
        if self.curve == "native":
            scale = Transition(1, 1.2, rate=there_and_back)
        elif self.curve == "keyframes":
            scale = Keyframes(Keyframe(0, 1), Keyframe(0.5, 1.2), Keyframe(1, 1))
        elif self.curve == "function":
            scale = lambda p: 1 + 0.2 * (1 - abs(2 * p - 1))
        elif self.curve == "product":
            scale = Transition(2, 2.4, rate=there_and_back)
        else:
            raise ValueError("curve must be native, keyframes, function or product")
        mode = "multiply" if self.curve == "product" else "replace"
        if self.target == "group":
            targets = (self.syllables,)
        elif self.target == "characters":
            targets = (self.characters, self.rubies)
        else:
            raise ValueError("target must be group or characters")
        for target in targets:
            target.on_singing(scale=scale, compose=mode)
            if self.curve == "product":
                target.on_singing(scale=0.5, compose=mode)
        halo = self.query_one("#active", Halo)
        if self.curve == "product":
            halo.on_singing(opacity=(0.5, 1), keep=True, compose="multiply")
            halo.on_singing(opacity=0.8, keep=True, compose="multiply")
        else:
            halo.on_singing(opacity=(0.4, 0.8), keep=True)
        if self.translate:
            if self.additive_offsets:
                for _ in range(2):
                    self.syllables.on_singing(
                        offset_x=(0, 10), offset_y=(0, -5), compose="add"
                    )
                    if self.target == "characters":
                        self.rubies.on_singing(
                            offset_x=(0, 10), offset_y=(0, -5), compose="add"
                        )
                return
            x = (lambda p: 20 * p) if self.curve == "function" else (0, 20)
            y = (lambda p: -10 * p) if self.curve == "function" else (0, -10)
            self.syllables.on_singing(offset_x=x, offset_y=y)
            if self.target == "characters":
                self.rubies.on_singing(offset_x=x, offset_y=y)

    def tracks(self, layout):
        box = layout.units[0].box
        region = Region(box.left, box.right)
        return (
            HighlightTrack("main", 0, (SingingPass(1000, 2000, region),)),
            HighlightTrack(
                "echo", 0, (SingingPass(1200, 1800, region),), end_behavior="hide"
            ),
        )
