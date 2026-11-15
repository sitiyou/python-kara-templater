"""与 layered_glow 等价的普通子类复用版本，可用 CLI --script 加载。"""

from examples.layered_glow import SUNG, glow_body, glow_ruby
from kara_templater import (
    Animation,
    FadeInAnimation,
    FadeOutAnimation,
    LineMatch,
    Overlay,
    ProgressCurve,
    SingingPulseAnimation,
    SourceMatch,
    Sweep,
    Track,
)


class LayeredGlow(Track):
    """Reusable defaults through an ordinary, explicitly typed constructor."""

    def __init__(
        self,
        *,
        source: SourceMatch,
        animations: tuple[Animation, ...] | None = None,
    ) -> None:
        super().__init__(
            source=source,
            body=glow_body(),
            ruby=glow_ruby(),
            overlay=Overlay(
                style=SUNG,
                reveal=Sweep(
                    curve=ProgressCurve.two_stage(
                        time_fraction=3 / 17,
                        progress_fraction=0.3,
                    )
                ),
            ),
            animations=(
                FadeInAnimation(duration=800),
                FadeOutAnimation(duration=200),
                SingingPulseAnimation(peak=1.1, attack=80, release=160),
            )
            if animations is None
            else animations,
        )


class Lead(Track):
    def __init__(self, *, source: SourceMatch) -> None:
        super().__init__(
            source=source,
            body=glow_body(),
            overlay=Overlay(style=SUNG),
            animations=(FadeInAnimation(duration=800), FadeOutAnimation(duration=200)),
        )


tracks = (
    LayeredGlow(source=LineMatch(style="K1")),
    LayeredGlow(source=LineMatch(style="K2")),
    Lead(source=LineMatch(style="LEAD")),
)
