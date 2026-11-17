"""Disjoint, priority, and layered highlights on the same lyric segment.

Run from a checkout: python -m examples.parallel_tracks output.ass
Edit highlight clocks, regions, styles, and opacity without splitting the lyrics.
"""

import argparse
from pathlib import Path

from kara_templater import (
    Color,
    Document,
    Highlight,
    HighlightPass,
    Layout,
    Line,
    LyricHighlights,
    LyricLine,
    Region,
    Scene,
    SceneBudget,
    StatePatch,
    Style,
    Track,
    Vec2,
    prepare_tracks,
)
from kara_templater.scene_animation import TimeSpan

SWEEP_CYAN = Color.hex("#33ddff")
ECHO_PINK = Color.hex("#ff5599")
# Three simultaneous ownership modes reserve conservative disjoint clip strips.
BUDGET = SceneBudget(max_events=50_000)


def disjoint(line: LyricLine) -> tuple[Highlight, ...]:
    box = line.layout.body.bounds
    whole = Region(box.left, box.right)
    return tuple(
        Highlight(
            name,
            0,
            (HighlightPass(TimeSpan(1, 2.4), region),),
            StatePatch(fill=SWEEP_CYAN),
        )
        for name, region in (
            ("left", Region(whole.left, whole.center)),
            ("right", Region(whole.center, whole.right)),
        )
    )


def overlapping(line: LyricLine, *, opacity: float = 1) -> tuple[Highlight, ...]:
    box = line.layout.body.bounds
    whole = Region(box.left, box.right)
    return (
        Highlight(
            "main",
            0,
            (HighlightPass(TimeSpan(1, 2.4), whole),),
            StatePatch(fill=SWEEP_CYAN, opacity=opacity),
        ),
        Highlight(
            "echo",
            0,
            (HighlightPass(TimeSpan(1.2, 2), whole),),
            StatePatch(fill=ECHO_PINK, opacity=opacity),
            priority=10,
            end="hide",
        ),
    )


def layered(line: LyricLine) -> tuple[Highlight, ...]:
    return overlapping(line, opacity=0.5)


def build() -> Scene:
    styles = tuple(
        Style(
            name=name,
            fontname="DejaVu Sans",
            fontsize=52,
            outline=0,
            shadow=0,
        )
        for name in ("regions", "priority", "layer")
    )
    document = Document.create(width=640, height=480, styles=styles)
    for style in styles:
        document.records.append(
            Line(
                start_time=1000,
                end_time=2400,
                style=style.name,
                text=r"{\c&HA0A0A0&\k140}Karaoke",
            )
        )
    configurations = tuple(
        Track(
            id=name,
            source=lambda source, name=name: source.style == name,
            layout=Layout(position=Vec2(160, y)),
            preview=1,
            tail=0.6,
            effects=(LyricHighlights(highlights=factory, mode=mode),),
        )
        for name, y, factory, mode in (
            ("regions", 60, disjoint, "union"),
            ("priority", 200, overlapping, "priority"),
            ("layer", 340, layered, "layer"),
        )
    )
    return prepare_tracks(document, tracks=configurations, owner="parallel-example")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = build().compile(budget=BUDGET)
    result.document.save(args.output)
    print(f"{result.event_count} events; {result.peak_active} active")


if __name__ == "__main__":
    main()
