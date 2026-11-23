# Eight karaoke motion studies

These studies compare different motion mechanisms using one lyric fixture:
250 ms, 250 ms, 1 s and 2 s singing units, plus an independent harmony track.
The Japanese variant adds ruby. Each recipe isolates one animation technique.

![Eight Japanese karaoke motion studies](../examples/assets/lyric-studies.gif)

Run the [complete example](../../examples/lyric_studies.py):

```sh
uv run python -m examples.lyric_studies build/sweep.ass --effect sweep
uv run python -m examples.lyric_studies build/echo.hook --effect echo
```

The overview records the former ASS renderer. The source includes additional
scene construction studies for inspecting timing and geometry.

## What differs

| `--effect` | Composition in the example |
| --- | --- |
| `sweep` | Stationary glyphs, singing color, independent line fades |
| `emphasis` | Singing-relative pulse plus a separate copy arriving from above |
| `scatter` | Seeded rotating exits, staggered at the end of the row |
| `curve` | Delayed curved copies and luminous path segments with following tails |
| `writing` | Initially hidden text revealed by the singing front, with persistent dust |
| `petals` | Characters and ruby depart after singing; petal particles have independent lifetimes |
| `echo` | Continuously rising, fading copies while the main baseline stays put |
| `sparkles` | Decorations follow the singing front over already visible text |

## Built-ins and custom animation

Rules own selection and time. Built-ins own reusable motion. Custom transforms
describe relative changes over normalized progress and use the same evaluator.
For example, the emphasis rule is:

```python
from kara_templater import LyricRule, ScalePulse

pulse = LyricRule("character", "singing", ScalePulse(peak=1.12, peak_at=0.42))
```

Its duration is the source singing interval. On a 250 ms note the peak is at
105 ms; on a 2 s note it is at 840 ms. Both phases ease to zero velocity at their
endpoints. The scale factor is an explicit artistic choice in this fixture;
equal amplitude need not be appropriate for very short notes in a finished song.

For an independent custom motion, a curved offset needs only progress functions:

```python
from kara_templater import Transform, Vec2

arc = Transform(
    offset=lambda p: Vec2(-36 * p, -80 * p * (1 - p)),
    opacity=lambda p: 1 - p,
)
```

A custom particle factory supplies shape and lifetime; the lyric emitter
supplies positions, births and identities. For a continuous luminous strand,
use `Ribbon()` or customize the [shared path trail](../guides/geometry.md#path-trails). No author code computes glyph
clip coordinates, searches internal object IDs or schedules individual letters.

## Copies, exits and reveal

`LyricEcho.animation` accepts a built-in, `Transform`, or `Timeline.animation`.
The sequence is fitted to the copy's `duration`. Default pivots use the measured
glyph center. Negative `delay` permits pre-onset arrival; copies cannot start
before Scene zero. Copies use the prepared static glyph appearance, not snapshots
of its animated history. Original singing clocks remain untouched.

`LyricRule(..., "exit", ..., stagger=0.04)` spaces exits in selection order.
The last selected target finishes at the display end; earlier targets finish
earlier. The layout reserves the full duration plus stagger. For per-character
departure after singing, use `after_singing` and an `offset` pause instead.
The fixture binds both characters and ruby when they leave; animating only the
body intentionally leaves its independently selected ruby unaffected.

For particle writing, hide only the unsung material:

```python
from kara_templater import CYAN, LyricHighlights, StatePatch

reveal = LyricHighlights.from_singing(
    StatePatch(fill=CYAN), base_paint=StatePatch(opacity=0),
)
```

The highlighted drawing starts from the original appearance before applying its
paint, so hiding the base does not hide the revealed text. `base_paint` accepts
paint/opacity properties, not position, scale or rotation. Ordinary sparkles keep
the default visible base, making these two effects visibly different.

## Cost and current limits

Hook output supports the sweep and echo studies. The sweep also exports to native ASS.

See [animation and timing](../guides/animation.md) for approximation contracts,
[particles](../guides/particles.md) for the custom factory protocol, and
[materials](../guides/materials.md) for the limits of ASS gradients and clipping.

## Independent ornament and text clocks

```sh
uv run python -m examples.lyric_ornament build/lyric-ornament.ass
```

![Stationary arch with independent exits](../examples/assets/lyric-ornament.gif)

The ornament example places nine stationary dots on an arch. Characters fade
from left to right and the dots fade from right to left. Each decoration
reserves its lifetime through the same layout allocator.
