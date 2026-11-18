"""Render one built-in animation on identical Japanese lyrics and real note lengths.

uv run python -m examples.karaoke_catalog build/studio.ass --entry petal --exit snow
"""

import argparse
from pathlib import Path
from typing import get_args

from kara_templater import (
    Box,
    Document,
    KaraokeDecoration,
    KaraokeEffects,
    KaraokeEntry,
    KaraokeExit,
    KaraokeSinging,
    Layout,
    Line,
    LyricScene,
    SceneBudget,
    Style,
    Track,
    prepare_tracks,
)

DEFAULTS = KaraokeEffects()


def build(
    *,
    entry: KaraokeEntry = DEFAULTS.entry,
    exit: KaraokeExit = DEFAULTS.exit,
    singing: KaraokeSinging = DEFAULTS.singing,
    decoration: KaraokeDecoration = DEFAULTS.decoration,
    stroke_flash: bool = False,
    recipe: KaraokeEffects | None = None,
) -> LyricScene:
    """One common scene; switch a single option to compare the catalog."""
    doc = Document.create(
        width=640,
        height=360,
        styles=(
            Style(
                name="Default",
                fontname="Sarasa UI J",
                fontsize=64,
                bold=True,
                outline=2,
                shadow=0,
            ),
        ),
    )
    doc.records.append(
        Line(start_time=1400, end_time=4200, text=r"{\k35}君{\k35}と{\k70}空{\k140}へ")
    )
    return prepare_tracks(
        doc,
        tracks=(
            Track(
                id="main",
                region=Box(40, 100, 560, 180),
                layout=Layout(alignment="center"),
                preview=1.1,
                tail=1.1,
                effects=(
                    recipe
                    or KaraokeEffects(
                        entry=entry,
                        exit=exit,
                        singing=singing,
                        decoration=decoration,
                        stroke_flash=stroke_flash,
                        seed=17,
                    ),
                ),
            ),
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    for name, alias, default in (
        ("entry", KaraokeEntry, DEFAULTS.entry),
        ("exit", KaraokeExit, DEFAULTS.exit),
        ("singing", KaraokeSinging, DEFAULTS.singing),
        ("decoration", KaraokeDecoration, DEFAULTS.decoration),
    ):
        parser.add_argument(
            f"--{name}", choices=get_args(alias.__value__), default=default
        )
    parser.add_argument("--stroke-flash", action="store_true")
    args = parser.parse_args()
    scene = build(
        entry=args.entry,
        exit=args.exit,
        singing=args.singing,
        decoration=args.decoration,
        stroke_flash=args.stroke_flash,
    )
    result = scene.compile(native_tweens=True, budget=SceneBudget(fps=60))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result.document.save(args.output)
    print(f"{result.event_count} events / {result.byte_count} bytes")


if __name__ == "__main__":
    main()
