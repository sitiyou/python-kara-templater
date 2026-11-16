"""Compare character-arrival, simultaneous-character and syllable animations.

python -m examples.output_layers build/layers.ass
All three rows bind the same custom animation and use ordinary Scene compilation.
"""

import argparse
from pathlib import Path

from kara_templater import (
    Color,
    Document,
    FadeIn,
    FadeOut,
    Highlight,
    HighlightArrival,
    HighlightPass,
    Layout,
    Line,
    LyricHighlights,
    LyricLine,
    LyricRule,
    LyricScene,
    LyricTarget,
    Region,
    ScalePulse,
    SceneResult,
    StateAnimation,
    StatePatch,
    Style,
    TimeSpan,
    Track,
    Vec2,
    prepare_tracks,
)


def pulse(line: LyricLine, target: LyricTarget) -> StateAnimation:
    if target.role == "syllable":
        return ScalePulse()  # Syllable groups already use the body center.
    character = next(
        character
        for item, character in zip(
            line.query("character"), line.layout.body.characters, strict=True
        )
        if item.id == target.id
    )
    scale = character.layout_scale
    assert scale is not None
    return ScalePulse(
        Vec2(
            character.bounds.width / (2 * scale.x),
            character.bounds.height / (2 * scale.y),
        )
    )


def highlights(line: LyricLine) -> tuple[Highlight, ...]:
    box = line.layout.body.bounds
    return (
        Highlight(
            "sung",
            0,
            (HighlightPass(TimeSpan(1, 2), Region(box.left, box.right)),),
            StatePatch(fill=Color.hex("#33ddff")),
        ),
    )


def build(
    text: str = "Karaoke",
    *,
    spacing: float = 0,
    fontname: str = "DejaVu Sans",
    italic: bool = False,
) -> LyricScene:
    """Build three independent streams, with no manual per-character scheduling."""
    styles = tuple(
        Style(
            name=f"Mode{index}",
            fontname=fontname,
            italic=italic,
            fontsize=52,
            align=8,
            margin_v=60 + 140 * index,
            spacing=spacing,
            outline=0,
            shadow=0,
        )
        for index in range(3)
    )
    document = Document.create(width=640, height=480, styles=styles)
    for style in styles:
        document.records.append(
            Line(
                start_time=1000,
                end_time=2000,
                style=style.name,
                text=r"{\c&HDDDDDD&\k100}" + text,
            )
        )
    rules = (
        LyricRule("character", HighlightArrival(highlights=highlights), pulse),
        LyricRule("character", "singing", pulse),
        LyricRule("syllable", "singing", pulse),
    )
    return prepare_tracks(
        document,
        tracks=tuple(
            Track(
                id=style.name,
                source=lambda source, name=style.name: source.style == name,
                layout=Layout(position=Vec2(0, style.margin_v), alignment="center"),
                preview=1,
                tail=1,
                animations=(
                    LyricRule("line", "enter", FadeIn(), duration=0.3),
                    rule,
                    LyricRule("line", "exit", FadeOut(), duration=0.3),
                ),
                factory=LyricHighlights(highlights=highlights).apply,
            )
            for style, rule in zip(styles, rules, strict=True)
        ),
        owner="pulse-comparison",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result: SceneResult = build().compile()
    result.document.save(args.output)
    print(f"{result.event_count} events; {result.peak_active} active; {args.output}")


if __name__ == "__main__":
    main()
