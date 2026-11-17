"""Eight source-inspired motion studies sharing the same lyric clocks.

uv run python -m examples.lyric_studies build/study.ass --effect petals
These are mechanism studies, not frame-exact reproductions of reference videos.
"""

import argparse
from pathlib import Path
from typing import Literal

from kara_templater import (
    CYAN,
    PINK,
    Box,
    Color,
    CurveIn,
    Document,
    DriftOut,
    FadeIn,
    FadeOut,
    Layout,
    Lifetime,
    Line,
    LyricEcho,
    LyricEffect,
    LyricHighlights,
    LyricParticles,
    LyricRule,
    LyricScene,
    ParticleContext,
    PathObject,
    Petal,
    Ribbon,
    ScalePulse,
    ScatterOut,
    SceneBudget,
    Sparkle,
    StatePatch,
    Style,
    Timeline,
    Track,
    Transform,
    Vec2,
    VectorPath,
    VisualState,
    linear_rate,
    prepare_tracks,
)

type Effect = Literal[
    "sweep", "emphasis", "scatter", "curve", "writing", "petals", "echo", "sparkles"
]
EFFECTS: tuple[Effect, ...] = (
    "sweep",
    "emphasis",
    "scatter",
    "curve",
    "writing",
    "petals",
    "echo",
    "sparkles",
)


def writing_dust(context: ParticleContext) -> PathObject:
    """Custom particles need only shape, relative motion and lifetime."""
    travel = Vec2(context.uniform("wind", -24, 24), context.uniform("rise", -30, -8))
    return PathObject(
        id=context.id,
        lifetime=Lifetime(context.birth, context.birth + 0.7),
        path=VectorPath.circle(context.uniform("size", 0.8, 1.8)),
        state=VisualState(position=context.position, fill=CYAN),
        layer=1,
    ).animate(
        Transform(
            offset=lambda p: travel * p,
            opacity=lambda p: (1 - p) ** 2,
        ),
        duration=0.7,
    )


def build(effect: Effect = "sweep", *, japanese: bool = False) -> LyricScene:
    """Bind built-ins/custom curves to short/held notes and an independent harmony."""
    if effect not in EFFECTS:
        raise ValueError(f"unknown study: {effect}")
    font = "Sarasa UI J" if japanese else "DejaVu Sans"
    styles = (
        Style(name="Main", fontname=font, fontsize=42, outline=1.5, shadow=0),
        Style(name="Main-furigana", fontname=font, fontsize=18, outline=1, shadow=0),
        Style(name="Harmony", fontname=font, fontsize=22, outline=1, shadow=0),
    )
    doc = Document.create(width=640, height=360, styles=styles)
    text = (
        r"{\k25}君|きみ{\k25}と{\k100}空|そら{\k200}へ"
        if japanese
        else r"{\k25}We {\k25}can {\k100}still {\k200}shine"
    )
    doc.records.extend(
        (
            Line(start_time=1000, end_time=4500, style="Main", text=text),
            Line(start_time=2500, end_time=4500, style="Harmony", text=r"{\k200}Ah"),
        )
    )
    effects: list[LyricEffect] = [
        LyricRule("line", "enter", FadeIn(), duration=0.2),
        LyricHighlights.from_singing(
            StatePatch(fill=CYAN, outline=Color.hex("#183744"), border=2),
            base_paint=StatePatch(opacity=0) if effect == "writing" else StatePatch(),
        ),
    ]
    match effect:
        case "emphasis":
            effects.append(
                LyricRule("character", "singing", ScalePulse(peak=1.12, peak_at=0.42))
            )
            effects.append(
                LyricEcho(
                    count=1,
                    offset=Vec2(),
                    delay=-0.2,
                    duration=0.65,
                    opacity=0.7,
                    paint=StatePatch(fill=PINK),
                    animation=Timeline()
                    .play(
                        CurveIn(
                            offset=Vec2(0, -32), bend=Vec2(0, -8), scale=1.3, rotation=0
                        ),
                        duration=0.2,
                    )
                    .play(FadeOut(), duration=0.45)
                    .animation,
                )
            )
        case "scatter":
            effects.extend(
                LyricRule(role, "exit", ScatterOut(seed=42), duration=0.5, stagger=0.04)
                for role in ("character", "ruby")
            )
        case "curve":
            effects.extend(
                (
                    LyricEcho(
                        count=3,
                        spacing=0.07,
                        offset=Vec2(),
                        delay=-0.3,
                        duration=0.75,
                        opacity=0.7,
                        paint=StatePatch(fill=PINK),
                        animation=Timeline()
                        .play(CurveIn(), duration=0.4)
                        .play(
                            FadeOut(),
                            duration=0.35,
                        )
                        .animation,
                    ),
                    LyricParticles(factory=Ribbon(), rate=6, seed=42),
                )
            )
        case "writing":
            effects.append(LyricParticles(factory=writing_dust, rate=28, seed=42))
        case "petals":
            effects.extend(
                LyricRule(role, "after_singing", DriftOut(), offset=0.14, duration=0.56)
                for role in ("character", "ruby")
            )
            effects.append(
                LyricParticles(
                    factory=Petal(size=3), placement="line", rate=12, seed=42
                )
            )
        case "echo":
            effects.append(
                LyricEcho(
                    count=2,
                    spacing=0.12,
                    duration=0.6,
                    opacity=0.8,
                    offset=Vec2(),
                    paint=StatePatch(fill=PINK),
                    animation=DriftOut(offset=Vec2(0, -54), scale=1, rate=linear_rate),
                )
            )
        case "sparkles":
            effects.append(LyricParticles(factory=Sparkle(size=3), rate=18, seed=42))
    if effect not in ("scatter", "petals"):
        effects.append(LyricRule("line", "exit", FadeOut(), duration=0.25))
    return prepare_tracks(
        doc,
        tracks=(
            Track(
                id="main",
                source=lambda source: source.style == "Main",
                styles=styles,
                region=Box(32, 160, 576, 160),
                layout=Layout(alignment="center"),
                effects=tuple(effects),
            ),
            Track(
                id="harmony",
                source=lambda source: source.style == "Harmony",
                styles=styles,
                region=Box(32, 20, 576, 70),
                layout=Layout(alignment="center"),
                effects=(
                    LyricRule("line", "exit", FadeOut(), duration=0.3),
                    LyricHighlights.from_singing(StatePatch(fill=PINK)),
                ),
            ),
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--effect", choices=EFFECTS, default="sweep")
    parser.add_argument("--japanese", action="store_true")
    args = parser.parse_args()
    result = build(args.effect, japanese=args.japanese).compile(
        native_tweens=True,
        budget=SceneBudget(fps=60),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result.document.save(args.output)
    print(
        f"{result.event_count} events, {result.byte_count} bytes, peak {result.peak_active}"
    )


if __name__ == "__main__":
    main()
