"""Independent lyric streams, reusable animations and an overridable allocator.

uv run python -m examples.lyric_orchestration build/unified/lyrics.ass
Use --rows 3 for the same built-in layout with three rows; --custom demonstrates
lead resets and a single-line exception using only allocate's public inputs.
Add --keep-rotation --advance-solo to change those choices inside the same
function. --dense includes overlapping singing that needs at least two rows.
"""

import argparse
from dataclasses import dataclass, replace
from pathlib import Path

from kara_templater import (
    CYAN,
    PINK,
    BarsCue,
    CueMarker,
    CuePreset,
    Document,
    FadeIn,
    FadeOut,
    Jump,
    Layout,
    LayoutContext,
    LayoutLine,
    Lifetime,
    Line,
    LyricRule,
    LyricScene,
    LyricSweep,
    PathObject,
    Placement,
    SceneBudget,
    Style,
    TextCue,
    Track,
    Vec2,
    VectorPath,
    VisualState,
    prepare_tracks,
)

BUDGET = SceneBudget(max_events=250_000, max_bytes=30 * 1024 * 1024)


@dataclass(frozen=True, kw_only=True)
class SongLayout(Layout):
    """Song-specific choices implemented entirely by the batch function."""

    reset_on_lead: bool = True
    advance_solo: bool = False

    def allocate(
        self, lines: tuple[LayoutLine, ...], context: LayoutContext
    ) -> tuple[Placement, ...]:
        placements: list[Placement] = []
        occupied: dict[int, int] = {}
        cursor = 0
        for line in lines:
            if line.lead and self.reset_on_lead:
                cursor = 0
            if "solo" in line.tags:
                placements.append(Placement(line.id, Vec2(300, 260), line.display))
                cursor += int(self.advance_solo)
                continue
            row = cursor % self.rows
            placement = super().allocate((line,), context)[0]
            placement = replace(
                placement,
                row=row,
                position=placement.position + Vec2(0, row * self.gap),
            )
            if row in occupied:
                previous = occupied[row]
                before = placements[previous]
                if lines[previous].required.end > line.required.start:
                    raise ValueError(f"{line.id}: reset would overlap {before.id}")
                if before.display.end > placement.display.start:
                    boundary = max(
                        lines[previous].required.end, placement.display.start
                    )
                    placements[previous] = replace(
                        before,
                        display=Lifetime(before.display.start, boundary),
                        adjustments=(
                            *before.adjustments,
                            f"tail shortened for {line.id}",
                        ),
                    )
                    placement = replace(
                        placement,
                        display=Lifetime(boundary, placement.display.end),
                        adjustments=(f"handoff after {before.id}",),
                    )
            occupied[row] = len(placements)
            placements.append(placement)
            cursor += 1
        return tuple(placements)


def song(*, dense: bool = False) -> Document:
    """One song for every layout; optionally include overlapping singing."""
    document = Document.create(
        width=960,
        height=540,
        styles=(
            Style(
                name="Main", fontname="DejaVu Sans", fontsize=48, shadow=0, outline=2
            ),
            Style(
                name="Harmony", fontname="DejaVu Sans", fontsize=32, shadow=0, outline=1
            ),
        ),
    )
    first_cue = CueMarker("count", "count", placement="independent").markup()
    lead = CueMarker("lead", "bars").markup()
    events = (
        (1, 2, first_cue + r"{\k50}When|wen{\k50} we|wi", ""),
        (
            2 if dense else 2.5,
            3 if dense else 3.5,
            r"{\k50}sing|sing{\k50} out|aut",
            "",
        ),
        (
            2.6 if dense else 4,
            3.6 if dense else 5,
            r"{\k40}Side|said{\k60} by side",
            "",
        ),
        (6, 7, lead + r"{\k40}Stay|stei{\kt60\k40}#|!stei", ""),
        (8, 9, r"{\k100}Solo", "solo"),
        (10, 11, r"{\k50}Here{\k50} again", ""),
    )
    for start, end, text, actor in events:
        document.records.append(
            Line(
                start_time=round(start * 1000),
                end_time=round(end * 1000),
                style="Main",
                actor=actor,
                text=text,
            )
        )
    document.records.append(
        Line(
            start_time=1000, end_time=4000, style="Harmony", text=r"{\k150}Ah{\k150} ah"
        )
    )
    return document


def build(*, layout: Layout | None = None, dense: bool = False) -> LyricScene:
    fade = FadeIn()
    main = Track(
        id="main",
        source=lambda source: source.style == "Main",
        layout=layout or Layout(rows=2, position=Vec2(100, 290), gap=80),
        tags=lambda source: frozenset((source.actor,)) if source.actor else frozenset(),
        animations=(
            LyricRule("line", "enter", fade, duration=0.15),
            LyricRule("line", "exit", FadeOut(), duration=0.15),
            LyricRule("segment", "singing", Jump(height=8)),
        ),
        cues={
            "bars": CuePreset(
                factory=BarsCue(width=60, height=30), lead=0.6, duration=0.6
            ),
            "count": CuePreset(factory=TextCue(font_size=36), position=Vec2(820, 80)),
        },
        factory=LyricSweep(fill=PINK, width=16, step=2).apply,
    )
    harmony = Track(
        id="harmony",
        source=lambda source: source.style == "Harmony",
        layout=Layout(position=Vec2(100, 50)),
        animations=(LyricRule("line", "enter", fade, duration=0.15),),
        factory=LyricSweep(fill=CYAN, width=12, step=2).apply,
    )
    scene = prepare_tracks(song(dense=dense), tracks=(main, harmony))
    accent = PathObject(
        id="accent",
        lifetime=Lifetime(0, 12),
        path=VectorPath.rectangle(8, 400),
        state=VisualState(position=Vec2(65, 50), fill=PINK),
    )
    scene.add(accent.animate(fade, duration=0.15))
    return scene


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--rows", type=int, default=2)
    parser.add_argument("--custom", action="store_true")
    parser.add_argument(
        "--keep-rotation", action="store_true", help="custom: ignore lead resets"
    )
    parser.add_argument(
        "--advance-solo", action="store_true", help="custom: advance on a solo line"
    )
    parser.add_argument(
        "--dense", action="store_true", help="include overlapping singing"
    )
    args = parser.parse_args()
    if not args.custom and (args.keep_rotation or args.advance_solo):
        parser.error("--keep-rotation and --advance-solo require --custom")
    layout = (
        SongLayout(
            rows=args.rows,
            position=Vec2(100, 290),
            gap=80,
            reset_on_lead=not args.keep_rotation,
            advance_solo=args.advance_solo,
        )
        if args.custom
        else Layout(rows=args.rows, position=Vec2(100, 290), gap=80)
    )
    result = build(layout=layout, dense=args.dense).compile(budget=BUDGET)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result.document.save(args.output)
    print(
        f"{result.event_count} events, {result.peak_active} active, {result.byte_count} bytes"
    )


if __name__ == "__main__":
    main()
