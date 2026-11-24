"""Independent lyric streams, reusable animations and an overridable allocator.

Pass a SongLayout to build(layout=...) to change how lead and solo lines use rows.
Use build(dense=True) to model overlapping lines.
"""

from dataclasses import dataclass, replace

from kara_templater import (
    CYAN,
    PINK,
    AssBudget,
    BarsCue,
    CueMarker,
    CuePreset,
    Document,
    FadeIn,
    FadeOut,
    Jump,
    Layout,
    LayoutContext,
    Lifetime,
    Line,
    LineLayoutRequest,
    LyricHighlights,
    LyricRule,
    LyricScene,
    PathObject,
    Placement,
    StatePatch,
    Style,
    TextCue,
    Track,
    Vec2,
    VectorPath,
    VisualState,
    build_lyric_scene,
)

BUDGET = AssBudget(max_events=250_000, max_bytes=30 * 1024 * 1024)


@dataclass(frozen=True, kw_only=True)
class SongLayout(Layout):
    """Song-specific choices implemented entirely by the batch function."""

    reset_on_lead: bool = True
    advance_solo: bool = False

    def allocate(
        self, lines: tuple[LineLayoutRequest, ...], context: LayoutContext
    ) -> tuple[Placement, ...]:
        placements: list[Placement] = []
        occupied: dict[int, int] = {}
        cursor = 0
        for line in lines:
            if line.lead and self.reset_on_lead:
                cursor = 0
            if "solo" in line.tags:
                placements.append(Placement(line.id, Vec2(300, 260), line.requested_display))
                cursor += int(self.advance_solo)
                continue
            row = cursor % self.rows
            placement = super().allocate((line,), context)[0]
            placement = replace(
                placement,
                row=row,
            )
            if row in occupied:
                previous = occupied[row]
                before = placements[previous]
                if lines[previous].required_display.end > line.required_display.start:
                    raise ValueError(f"{line.id}: reset would overlap {before.id}")
                if before.display.end > placement.display.start:
                    boundary = max(
                        lines[previous].required_display.end, placement.display.start
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
        offsets = self.row_offsets(lines, tuple(placements))
        return tuple(replace(p, position=p.position + Vec2(0, offsets.get(p.id, 0))) for p in placements)


def song(*, dense: bool = False) -> Document:
    """One song for every layout; optionally include overlapping timing."""
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
        tail=1.0,  # This example compares layouts with fixed-duration animation rules.
        source=lambda source: source.style == "Main",
        layout=layout or Layout(rows=2, position=Vec2(100, 290)),
        tags=lambda source: frozenset((source.actor,)) if source.actor else frozenset(),
        effects=(
            LyricRule("line", "enter", fade, duration=0.15),
            LyricRule("line", "exit", FadeOut(), duration=0.15),
            LyricRule("segment", "timing", Jump(height=8)),
            LyricHighlights.from_timing(StatePatch(fill=PINK), hook_feather=16),
        ),
        cues={
            "bars": CuePreset(
                # Keep the reset cue in the same 0.6 s window for each layout comparison.
                factory=BarsCue(width=60, height=30), duration=0.6, lead=0.6
            ),
            "count": CuePreset(factory=TextCue(font_size=36), position=Vec2(820, 80)),
        },
    )
    harmony = Track(
        id="harmony",
        source=lambda source: source.style == "Harmony",
        layout=Layout(position=Vec2(100, 50)),
        effects=(
            LyricRule("line", "enter", fade, duration=0.15),
            LyricHighlights.from_timing(StatePatch(fill=CYAN), hook_feather=12),
        ),
    )
    scene = build_lyric_scene(song(dense=dense), tracks=(main, harmony))
    accent = PathObject(
        id="accent",
        lifetime=Lifetime(0, 12),
        path=VectorPath.rectangle(8, 400),
        state=VisualState(position=Vec2(65, 50), fill=PINK),
    )
    scene.add(accent.animate(fade, duration=0.15))
    return scene
