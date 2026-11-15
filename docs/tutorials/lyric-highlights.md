# Add custom motion to lyric highlights

This complete script constructs a small timed lyric, prepares editable Track
objects, and makes each drawable character hop when the singing front arrives.
It uses only the installed library and writes `lyric-arc.ass`.

```python
from math import pi, sin

from kara_templater import (
    CYAN,
    WHITE,
    Body,
    Document,
    FadeInAnimation,
    FadeOutAnimation,
    HighlightAnimation,
    ImportSettings,
    Line,
    LineMatch,
    Overlay,
    PaintStyle,
    Pulse,
    SingleLine,
    Style,
    TextStyle,
    Track,
    prepare_tracks,
)

document = Document.create(
    width=640,
    height=360,
    styles=(Style(fontname="DejaVu Sans", fontsize=44, align=5, shadow=0),),
)
document.records.append(Line(
    text=r"{\k100}Sing {\k100}with {\k100}me",
    start_time=1000,
    end_time=4000,
))
track = Track(
    source=LineMatch(),
    body=Body(style=TextStyle(fill=WHITE)),
    overlay=Overlay(style=PaintStyle(fill=CYAN)),
    layout=SingleLine(position=(320, 180)),
    animations=(
        FadeInAnimation(duration=200),
        HighlightAnimation(
            trigger=Pulse(duration_ms=400),
            offset_y=lambda progress: -20 * sin(pi * progress),
        ),
        FadeOutAnimation(duration=200),
    ),
)
prepared = prepare_tracks(
    document,
    tracks=(track,),
    import_settings=ImportSettings(lead_ms=500, tail_ms=500),
)
result = prepared.compile()
result.document.save("lyric-arc.ass")
print(result.event_count, result.peak_active, result.byte_count)
```

## Keep the clocks separate

The input Line starts at 1000 milliseconds; each `\k100` contributes one second
of singing. ImportSettings adds display time before and after the event without
shifting those singing intervals. Fades use the display boundary. HighlightAnimation
gives each character a separate 400 ms arc starting at its measured highlight
arrival, even though each word has one original karaoke segment.

Editable mode is the default: property functions run during Scene compilation,
where SceneBudget controls sampling and total output. Use native mode explicitly
when you need native interpolation or source styles that editable text does not
support. Their between-sample semantics differ.

## Use your own source and objects

Replace the Document construction with `Document.load("input.ass")` to style a
supported lyric input. Narrow LineMatch if you want only particular styles or
text. The [Document guide](../guides/documents.md) describes supported input
semantics and source preservation.

Before compiling, add decorations to `prepared.scene` or edit its ObjectGroups
using dataclasses.replace. The spark factory from the
[custom animation tutorial](custom-animation.md) produces ordinary PathObjects
that can be added to the same Scene. For ruby and cue content, see
[text and cues](../guides/text-and-cues.md).
