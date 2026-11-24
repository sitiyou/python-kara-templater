"""Compare character-arrival, simultaneous-character and syllable animations.

All three rows bind the same custom animation and use ordinary Scene compilation.
"""


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
    Region,
    ScalePulse,
    StatePatch,
    Style,
    TimeSpan,
    Track,
    Vec2,
    build_lyric_scene,
)


def highlights(line: LyricLine) -> tuple[Highlight, ...]:
    box = line.layout.body.bounds
    return (
        Highlight(
            "highlight",
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
        LyricRule("character", HighlightArrival(highlights=highlights), ScalePulse()),
        LyricRule("character", "timing", ScalePulse()),
        LyricRule("syllable", "timing", ScalePulse()),
    )
    return build_lyric_scene(
        document,
        tracks=tuple(
            Track(
                id=style.name,
                source=lambda source, name=style.name: source.style == name,
                layout=Layout(position=Vec2(0, style.margin_v), alignment="center"),
                preview=1,
                tail=1,
                effects=(
                    LyricRule("line", "enter", FadeIn(), duration=0.3),
                    rule,
                    LyricRule("line", "exit", FadeOut(), duration=0.3),
                    LyricHighlights(highlights=highlights),
                ),
            )
            for style, rule in zip(styles, rules, strict=True)
        ),
        owner="pulse-comparison",
    )
