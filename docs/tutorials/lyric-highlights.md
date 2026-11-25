# Animate the highlight

Trigger a character animation at the exact moment the karaoke highlight sweep reaches each glyph. Use this pattern when a jump, pulse, or accent must stay locked to the moving sweep front instead of starting on the whole syllable at once.

## Bind motion to the sweep front

This complete script fades a line in and out while bouncing every character upward by 24 px as the cyan sweep passes through it. It uses only the installed library and writes `lyric-arc.hook`.

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
    build_lyric_scene,
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
                    TimeSpan(segment.timing.start, segment.timing.end),
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


scene = build_lyric_scene(
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
                LyricHighlights.from_timing(StatePatch(fill=CYAN)),
            ),
        ),
    ),
)
scene.export("lyric-arc.hook", fps=60)
```

## How arrival timing works

The `highlights` factory turns each timed syllable into a `Highlight` made of one or more `HighlightPass` intervals over that syllable's measured horizontal `Region`.

Passing `HighlightArrival(highlights=highlights)` as the anchor of `LyricRule` computes when the sweep crosses each measured character, without a manual character loop or hand-calculated timestamps. By default, each character's animation starts when the front enters it (`threshold="enter"`) and lasts for the full time the front takes to cross that glyph.

Adjust how arrivals trigger with `HighlightArrival` and `LyricRule` options:

| Option | Where to set it | What it changes |
| --- | --- | --- |
| `duration=0.25` | `LyricRule` | Uses a fixed animation length instead of the character's traversal duration |
| `threshold="center"` or `"complete"` | `HighlightArrival` | Starts the motion when the sweep reaches the glyph's midpoint or right edge |
| `selection="each"` | `HighlightArrival` | Triggers on every matching highlight rather than only the first per round |
| `names=frozenset(...)` | `HighlightArrival` | Restricts triggers to specific named highlights |
| `retrigger=False` | `HighlightArrival` | Fires only on the first crossing when a unit repeats |

> [!NOTE]
> If a `HighlightPass` uses a nonlinear `rate`, supply its matching `inverse_rate` as well. `HighlightArrival` computes exact crossing times from the inverse rather than approximating with a search.

## Slant the sweep for italic text

`LyricHighlights.from_timing` and `KaraokeEffects` automatically slant the sweep front on horizontal italic or oblique text, and a timed vector guide in a cue factory follows its own style.

To override the angle, pass `sweep_angle` in degrees:

- `sweep_angle=0` forces a vertical front even on italic text.
- Positive angles lean the top of the front to the right; negative angles lean it to the left.

```python
from kara_templater import CYAN, LyricHighlights, StatePatch

straight_sweep = LyricHighlights.from_timing(
    StatePatch(fill=CYAN),
    sweep_angle=0,
)
```

## Combine with line motion and custom animations

Whole-line animations and per-character highlight motion compose naturally through the scene hierarchy: the line's `FadeIn` and `FadeOut` apply on the parent group while `Jump` moves each character inside it. The highlight paint copy automatically follows its target glyph's motion.

Lyrics and ordinary scene objects share the same animation protocol. To replace `Jump(24)` with your own motion, pass a `Transform`, a `StateFunction`, a `ShaderMotion`, or a custom `StateAnimation` that declares its written channels.

## Next steps

- [Write a custom animation](custom-animation.md) to build your own GPU-accelerated motion function.
- [Animation and timing](../guides/animation.md) for built-in animations, easings, and `Timeline`.
- [Lay out vocal tracks](../guides/tracks.md) for `LyricRule` anchors, roles, and track composition.
- [API reference: Colors and appearance](../reference/paint.md) for `Highlight`, `HighlightPass`, `HighlightArrival`, and `LyricHighlights`.
