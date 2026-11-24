"""Render one built-in animation on identical Japanese lyrics and real note lengths.

uv run python -m examples.karaoke_catalog build/studio.hook --entry petal --exit snow
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
    KaraokeHighlight,
    Layout,
    Line,
    LyricScene,
    Style,
    Track,
    build_lyric_scene,
)

DEFAULTS = KaraokeEffects()


def build(
    *,
    entry: KaraokeEntry = DEFAULTS.entry,
    exit: KaraokeExit = DEFAULTS.exit,
    highlight: KaraokeHighlight = DEFAULTS.highlight,
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
    return build_lyric_scene(
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
                        highlight=highlight,
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
        ("highlight", KaraokeHighlight, DEFAULTS.highlight),
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
        highlight=args.highlight,
        decoration=args.decoration,
        stroke_flash=args.stroke_flash,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.suffix == ".hook":
        scene.export(args.output, fps=60)
        return
    result = scene.ass.compile()
    result.document.save(args.output)
    print(f"{result.event_count} events / {result.byte_count} bytes")


if __name__ == "__main__":
    main()
