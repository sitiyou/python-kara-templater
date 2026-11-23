# Add custom motion to lyric highlights

This complete script binds a shared jump animation when each measured character
is reached by the singing front. It uses only the installed library and writes
`lyric-arc.hook`. Lyrics and ordinary objects use the same animation protocol.

```python
from kara_templater import (
    CYAN,
    Document,
    FadeIn,
    FadeOut,
    Highlight,
    HighlightArrival,
    HighlightPass,
    Jump,
    Layout,
    Line,
    LyricHighlights,
    LyricLine,
    LyricRule,
    Region,
    StatePatch,
    Style,
    TimeSpan,
    Track,
    Vec2,
    prepare_tracks,
)

document = Document.create(
    width=640,
    height=360,
    styles=(Style(fontname="DejaVu Sans", fontsize=44, shadow=0),),
)
document.records.append(
    Line(
        text=r"{\k100}Sing {\k100}with {\k100}me",
        start_time=1000,
        end_time=4000,
    )
)


def highlights(line: LyricLine) -> tuple[Highlight, ...]:
    return tuple(
        Highlight(
            f"unit:{index}",
            index,
            tuple(
                HighlightPass(
                    TimeSpan(segment.singing.start, segment.singing.end),
                    Region(box.left, box.right),
                    round=round_id,
                )
                for round_id, segment in enumerate(unit.segments)
            ),
            StatePatch(fill=CYAN),
            repeat="reset",
        )
        for index, unit in enumerate(line.layout.lyrics.units)
        if unit.segments
        for box in (line.layout.body.range_bounds(unit.start, unit.end),)
    )


scene = prepare_tracks(
    document,
    tracks=(
        Track(
            id="main",
            layout=Layout(position=Vec2(70, 160)),
            effects=(
                LyricRule("line", "enter", FadeIn(), duration=0.25),
                LyricRule(
                    "character", HighlightArrival(highlights=highlights), Jump(24)
                ),
                LyricRule("line", "exit", FadeOut(), duration=0.4),
                LyricHighlights.from_singing(StatePatch(fill=CYAN)),
            ),
        ),
    ),
)
scene.export("lyric-arc.hook", fps=60)
```

The factory describes each syllable's measured region and original singing
passes. HighlightArrival computes character crossing times from those passes;
LyricRule binds Jump without a manual character loop or absolute animation times.
It defaults to a character's full traversal duration. Set `duration` on the rule
for a fixed length, or choose the center/complete threshold on HighlightArrival.

Whole-line fades and character jumps compose through the visual hierarchy.
Highlight paint copies follow their target's animation. Named highlight filters,
repeat rounds and nonlinear curves are explicit; nonlinear arrival calculations
require a declared inverse curve rather than an approximate search.

To supply a new motion, implement StateAnimation or use StateFunction, declaring
its written channels. The same animation can be bound directly to a TextObject,
a visual Group or a lyric rule. See [animation](../guides/animation.md) and
[Tracks](../guides/tracks.md) for timing, grouping and allocation contracts.
