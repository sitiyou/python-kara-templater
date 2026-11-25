# Motion studies

Compare eight karaoke motion patterns on one shared lyric fixture with quick notes, held notes, ruby readings, and an independent harmony track. Pick one mechanism that fits your song and test how it behaves across different note lengths before combining effects.

![Eight Japanese karaoke motion studies](../examples/assets/lyric-studies.gif)

The shared fixture times four units at 250 ms, 250 ms, 1 s, and 2 s, paired with a harmony track and an optional Japanese ruby variant. The preview above shows all eight studies rendered on that fixture (recorded from the former ASS renderer).

Run [lyric_studies.py](../../examples/lyric_studies.py) from a checkout:

```sh
uv run python -m examples.lyric_studies build/sweep.hook --effect sweep
uv run python -m examples.lyric_studies build/echo.hook --effect echo
```

The command-line interface exports the `sweep` and `echo` studies to Hook (`sweep` also exports to ASS). All eight studies are constructible in Python through `examples.lyric_studies.build(effect)` for scene inspection.

## Compare the eight studies

| Study | What it isolates |
| --- | --- |
| `sweep` | Stationary glyphs, timing color sweep, and independent line fades |
| `emphasis` | Timing-relative scale pulse plus a colored copy arriving from above |
| `scatter` | Seeded rotating exits staggered across the end of the row |
| `curve` | Delayed curved glyph copies paired with luminous ribbon trails |
| `writing` | Hidden base text revealed only by the timing front, plus rising dust particles |
| `petals` | Characters and ruby drift away after timing while petals fall on their own lifetimes |
| `echo` | Continuously rising, fading glyph copies while the main baseline stays still |
| `sparkles` | Sparkle particles follow the timing front across already visible text |

## Built-in rules and custom curves

`LyricRule` owns target selection and timing; built-in animations own reusable motion. Because `ScalePulse` binds to each timing interval, one rule adapts automatically to note length:

```python
from kara_templater import LyricRule, ScalePulse

pulse = LyricRule("character", "timing", ScalePulse(peak=1.12, peak_at=0.42))
```

On a 250 ms note the pulse peaks at 105 ms; on a 2 s note it peaks at 840 ms, easing smoothly to zero velocity at both ends. In a finished song you can scale the amplitude with note duration using an animation factory (see [lyric_pulse_drift.py](../../examples/lyric_pulse_drift.py)).

For custom relative motion without writing a full `StateAnimation`, `Transform` takes pure functions of normalized progress (`0` to `1`):

```python
from kara_templater import Transform, Vec2

arc = Transform(
    offset=lambda p: Vec2(-36 * p, -80 * p * (1 - p)),
    opacity=lambda p: 1 - p,
)
```

For emitted particles, supply a `ParticleFactory` that sets each particle's shape and lifetime while `LyricParticles` handles birth times, positions, and IDs. For luminous strands whose tails chase their heads, use `Ribbon()` or build a custom trail with `TrailPath` (see [Shapes, clips and masks](../guides/geometry.md)).

## Copies, staggered exits, and reveal-only text

`LyricEcho` spawns static copies of each glyph at its timing onset:

- `animation` accepts a built-in animation, a `Transform`, or `Timeline().animation`, stretched to the copy's `duration`.
- Pivots default to each measured glyph's center.
- Negative `delay` lets copies arrive before the note onset (clamped so nothing starts before scene time `0`).
- Copies capture the glyph's static prepared appearance rather than snapshots of earlier animations, leaving original timing clocks untouched.

For staggered row exits, pass `stagger` to an `"exit"` rule:

```python
from kara_templater import LyricRule, ScatterOut

exits = tuple(
    LyricRule(role, "exit", ScatterOut(seed=42), duration=0.5, stagger=0.04)
    for role in ("character", "ruby")
)
```

With `"exit"`, the last selected target finishes at the line's display end and earlier targets finish earlier; the layout reserves the full duration plus stagger. To send each glyph away right after its own note ends instead, anchor to `"after_timing"` with an `offset` pause. Binding both `"character"` and `"ruby"` moves readings with their characters; binding only `"character"` intentionally leaves ruby in place.

To reveal hidden text as the sweep passes (as in the `writing` study), hide only the base layer with `base_paint`:

```python
from kara_templater import CYAN, LyricHighlights, StatePatch

reveal = LyricHighlights.from_timing(
    StatePatch(fill=CYAN),
    base_paint=StatePatch(opacity=0),
)
```

The highlighted layer starts from the original visible glyph before applying its highlight paint, so setting `opacity=0` on `base_paint` reveals the text cleanly as the front moves. `base_paint` accepts paint and opacity fields only, not position, scale, or rotation.

> [!NOTE]
> Among the eight fixtures in `lyric_studies.py`, `sweep` and `echo` export directly to Hook (`sweep` also compiles to ASS). The other six combine Python `Transform`, `AnimationSequence`, deformed `Ribbon` paths, or overlapping line fades with particles to study scene-level composition; for Hook export, use `ShaderMotion` or `KaraokeEffects` presets instead.

## Independent ornament and text clocks

Decorations can live on their own clocks while still participating in the line's layout window.

![Stationary arch with independent exits](../examples/assets/lyric-ornament.gif)

Run [lyric_ornament.py](../../examples/lyric_ornament.py) to compile the ASS demo, or call `examples.lyric_ornament.build().export("lyric-ornament.hook")` for Hook output:

```sh
uv run python -m examples.lyric_ornament build/lyric-ornament.ass
```

The example places nine stationary dots along an arch above the text. After the last note, the characters fade left to right through a custom `row_end` anchor while the dots fade right to left on their own schedules. Track preparation detects every child's lifetime automatically and reserves enough display time for both.

## Next steps

- [Write a custom animation](custom-animation.md) to port a Python motion curve to `ShaderMotion` for Hook export.
- [Particles, copies and echoes](../guides/particles.md) for `LyricEcho`, `LyricParticles`, and custom `ParticleFactory` functions.
- [Animation and timing](../guides/animation.md) for `ScalePulse`, `Transform`, `Timeline`, and Hook-compilable motion.
- [Color and materials](../guides/materials.md) for `LyricHighlights`, gradients, and shader materials.
