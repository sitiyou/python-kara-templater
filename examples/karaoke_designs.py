"""Reference-informed karaoke styles on one original, shared lyric fixture.

uv run python -m examples.karaoke_designs build/broadcast.ass --style broadcast
Styles reproduce visual principles, not the original songs or exact fonts.
"""

import argparse
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal

from kara_templater import (
    WHITE,
    BarsCue,
    Box,
    Color,
    CueMarker,
    CuePreset,
    Document,
    FadeIn,
    FadeOut,
    Glow,
    Layout,
    LayoutContext,
    LayoutLine,
    Line,
    LyricAnimationContext,
    LyricHighlights,
    LyricLine,
    LyricRule,
    LyricScene,
    LyricTarget,
    Placement,
    SceneBudget,
    StateFunction,
    StatePatch,
    Style,
    Track,
    Vec2,
    VisualState,
    prepare_tracks,
)

type Design = Literal["broadcast", "amber", "candy"]


@dataclass(frozen=True, kw_only=True)
class OpposingRows(Layout):
    """Reuse occupancy allocation; right-align odd rows within the same region."""

    def allocate(
        self, lines: tuple[LayoutLine, ...], context: LayoutContext
    ) -> tuple[Placement, ...]:
        placements = super().allocate(lines, context)
        return tuple(
            replace(
                placement,
                position=placement.position
                + Vec2(context.region.width - line.bounds.width, 0),
            )
            if placement.row is not None and placement.row % 2
            else placement
            for line, placement in zip(lines, placements, strict=True)
        )


@dataclass(frozen=True)
class Palette:
    """Paint values are script pixels at 1280 × 720; RGB hex is author-facing."""

    unsung: str
    unsung_edge: str
    sung: str
    sung_edge: str
    halo: str
    blur: float
    halo_opacity: float
    font: str
    bold: bool


PALETTES: dict[Design, Palette] = {
    "broadcast": Palette(
        "#FFFFFF",
        "#20202A",
        "#E32442",
        "#FFFFFF",
        "#20202A",
        0.6,
        0.9,
        "DejaVu Sans",
        True,
    ),
    "amber": Palette(
        "#FFF9EA",
        "#805326",
        "#DB9A39",
        "#FFF9EA",
        "#DAA051",
        4,
        0.5,
        "DejaVu Serif",
        False,
    ),
    "candy": Palette(
        "#FFFBEF",
        "#816020",
        "#F53F85",
        "#FFFBEF",
        "#374946",
        0.5,
        0.9,
        "DejaVu Sans",
        True,
    ),
}


def ass_color(value: str) -> str:
    """Encode a palette color only where constructing an input ASS Style."""
    return f"&H00{value[5:7]}{value[3:5]}{value[1:3]}"


def song(
    palette: Palette, *, font: str | None = None, japanese: bool = False
) -> Document:
    """Original text: held notes, quick notes, ruby, cue and overlapping harmony."""

    family = font or (
        ("Noto Serif CJK JP" if not palette.bold else "Sarasa UI J")
        if japanese
        else palette.font
    )

    def style(name: str, size: float, border: float) -> Style:
        return Style(
            name=name,
            fontname=family,
            fontsize=size,
            bold=palette.bold,
            shadow=0,
            outline=border,
        )

    document = Document.create(
        width=1280,
        height=720,
        styles=(
            style("Main", 58, 2.5),
            style("Main-furigana", 24, 1),
            style("Harmony", 32, 1.5),
        ),
    )
    for item in document.styles.values():
        item.fields["PrimaryColour"] = ass_color(palette.unsung)
        item.fields["OutlineColour"] = ass_color(palette.unsung_edge)
    cue = CueMarker("lead", "bars").markup()
    rows = (
        (2, 4.5, cue + r"{\k50}Light|lait{\k50} up{\k150} the sky", "Main"),
        (4.7, 7.2, r"{\k25}Take{\k25} my{\k50} hand{\k150} tonight", "Main"),
        (7.4, 9.9, r"{\k100}Softly|soft-li{\k50} we{\k100} shine", "Main"),
        (10.1, 12.6, r"{\k15}One{\k15} more{\k20} beat{\k200} carries us", "Main"),
        (4.7, 8.7, r"{\k200}Ah{\k200} ah", "Harmony"),
    )
    if japanese:
        rows = (
            (2, 4.5, cue + r"{\k50}空|そら{\k50}へ{\k150}光を届けよう", "Main"),
            (4.7, 7.2, r"{\k25}君|きみ{\k25}と{\k50}声|こえ{\k150}を重ねよう", "Main"),
            (7.4, 9.9, r"{\k100}静|しず{\k50}かな{\k100}夢が輝く", "Main"),
            (10.1, 12.6, r"{\k15}も{\k15}う{\k20}一度|いちど{\k200}歌おう", "Main"),
            (4.7, 8.7, r"{\k200}Ah{\k200} ah", "Harmony"),
        )
    for start, end, text, name in rows:
        document.records.append(
            Line(
                start_time=round(start * 1000),
                end_time=round(end * 1000),
                text=text,
                style=name,
            )
        )
    return document


def candy_exit(timing: LyricAnimationContext) -> StateFunction:
    """A short staggered tilt; singing itself stays geometrically stationary."""
    targets = timing.line.query("character")
    index = next(i for i, item in enumerate(targets) if item.id == timing.target.id)
    delay = 0.45 * index / max(1, len(targets) - 1)

    def sample(state: VisualState, progress: float) -> VisualState:
        phase = min(1.0, max(0.0, (progress - delay) / 0.55))
        return replace(
            state,
            rotation=state.rotation + 24 * phase,
            position=state.position + Vec2(0, -12 * phase),
            opacity=state.opacity * (1 - phase),
        )

    return StateFunction(sample, frozenset(("rotation", "position", "opacity")))


def build(
    design: Design = "broadcast", *, font: str | None = None, japanese: bool = False
) -> LyricScene:
    palette = PALETTES[design]

    def halo(line: LyricLine, target: LyricTarget) -> Glow:
        scale = 24 / 58 if target.role == "ruby" else 1
        return Glow(
            Color.hex(palette.halo),
            palette.blur * scale,
            4.5 * scale,
            palette.halo_opacity,
        )

    highlighter = LyricHighlights.from_singing(
        StatePatch(fill=Color.hex(palette.sung), outline=Color.hex(palette.sung_edge)),
        base_glow=halo,
        glow=halo,
    )
    rules = (
        LyricRule("line", "enter", FadeIn(), duration=0.18),
        LyricRule("line", "exit", FadeOut(), duration=0.22),
    )
    if design == "candy":
        rules = (
            rules[0],
            LyricRule("character", "exit", candy_exit, duration=0.42),
            LyricRule("ruby", "exit", FadeOut(), duration=0.42),
        )
    return prepare_tracks(
        song(palette, font=font, japanese=japanese),
        tracks=(
            Track(
                id="main",
                source=lambda source: source.style == "Main",
                region=Box(72, 476, 1136, 220),
                layout=OpposingRows(rows=2, gap=108),
                preview=1.2,
                tail=0.35,
                effects=(
                    *(rules),
                    highlighter,
                ),
                cues={
                    "bars": CuePreset(
                        factory=BarsCue(
                            width=46,
                            height=26,
                            color=Color.hex(palette.sung),
                            outline=WHITE,
                            border=1,
                        ),
                        lead=0.8,
                        duration=0.8,
                    )
                },
            ),
            Track(
                id="harmony",
                source=lambda source: source.style == "Harmony",
                region=Box(72, 76, 1136, 100),
                layout=Layout(alignment="center"),
                preview=0.8,
                tail=0.3,
                effects=(
                    *(
                        (rules[0], rules[1])
                        if design != "candy"
                        else (
                            rules[0],
                            LyricRule("line", "exit", FadeOut(), duration=0.22),
                        )
                    ),
                    LyricHighlights.from_singing(
                        StatePatch(fill=Color.hex(palette.sung), outline=WHITE)
                    ),
                ),
            ),
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--style", choices=tuple(PALETTES), default="broadcast")
    parser.add_argument("--font", help="Installed font family; overrides body and ruby")
    parser.add_argument(
        "--japanese",
        action="store_true",
        help="Original Japanese lyrics; requires Sarasa UI J / Noto Serif CJK JP",
    )
    args = parser.parse_args()
    design: Design
    match args.style:
        case "broadcast":
            design = "broadcast"
        case "amber":
            design = "amber"
        case "candy":
            design = "candy"
        case _:
            raise ValueError("unknown design")
    result = build(design, font=args.font, japanese=args.japanese).compile(
        native_tweens=True,
        budget=SceneBudget(fps=60, max_events=40_000, max_bytes=20 * 1024 * 1024),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result.document.save(args.output)
    print(
        f"{result.event_count} events, {result.peak_active} active, {result.byte_count} bytes"
    )


if __name__ == "__main__":
    main()
