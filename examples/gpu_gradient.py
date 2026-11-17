"""One Scene, a continuous GPU gradient, and a small ordinary-ASS fallback.

Run: python -m examples.gpu_gradient
Then: kara-render build/gpu-gradient.ass background.mp4 build/gpu-gradient.mp4
"""

from pathlib import Path

from kara_templater import (
    Color,
    ColorRamp,
    ColorStop,
    Document,
    DriftOut,
    Lifetime,
    Line,
    LinearGradient,
    ScalePulse,
    Scene,
    TextObject,
    Vec2,
    VisualState,
    smoother_rate,
)


def build(document: Document) -> Scene:
    word = TextObject(
        id="lyric",
        text="Sing in color",
        font_size=56,
        lifetime=Lifetime(0, 3),
        state=VisualState(position=Vec2(100, 140), border=2),
        material=LinearGradient(
            axis="y",
            space="local",
            fill=ColorRamp(
                (
                    ColorStop(5, Color.hex("#60E8FF")),
                    ColorStop(65, Color.hex("#F075CB")),
                )
            ),
        ),
    ).animate(ScalePulse(peak=1.08, peak_at=0.42, rate=smoother_rate), duration=2.4)
    word = word.animate(DriftOut(offset=Vec2(15, -35)), at=2.4, duration=0.6)
    return Scene(document).add(word)


def main():
    fallback = Document.create(width=640, height=360)
    fallback.records.append(
        Line(
            text=r"{\an7\pos(100,140)\fnDejaVu Sans\fs56\shad0\kf240}Sing in color",
            end_time=3000,
        )
    )
    output = Path("build/gpu-gradient.ass")
    output.parent.mkdir(parents=True, exist_ok=True)
    build(fallback).enhance(fallback, fps=60).save(output)
    print(output)


if __name__ == "__main__":
    main()
