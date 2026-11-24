---
name: kara-templater
description: Design and verify Python karaoke templates with kara-templater for ASS and libplacebo hook output. Use for typography, ruby, vocal tracks, countdowns, highlight palettes, particles and animated lyric effects.
---

# Design a karaoke template

For a first standalone export, follow [Getting started](../../docs/getting-started.md).

Start with the smallest template that expresses the requested design. Leave optional arguments unset when the library already produces the intended result. Override a parameter for a user choice, a song-specific constraint, or a concrete issue seen in preview. For example, omitting `Track.preview` requests the library’s current lead time and lets the allocator fit it to each row. Treat numbers in examples and design recommendations as starting points.

Start with a short passage of timed lyrics from the song, a representative background and the intended canvas and frame rate. Select a passage with a held vowel, a quick row change and ruby. Include overlapping voices if the song has them.

For horizontal main vocals on a 1920 × 1080 canvas, start with 100 script pixels for the body and 45 for ruby. Scale both with canvas height. Adjust them for lyric length, typeface and visual style after previewing the longest line and the densest readings.

For a custom `Layout(rows=2)`, omit `gap` to fit the co-visible rows and their readings with 0.2 em of clearance. Set it only to match an intentional fixed row-origin distance. The default Track allocator, `KaraokeRows`, uses its own canvas-scaled spacing.

## Find the closest working example

Choose a row for the requested change. Inspect the rendered example and its source, then use the linked guide for the controls involved. For a broad visual brief, start with the [effect gallery](../../docs/examples/README.md).

| Request | Starting point | Check on the song |
| --- | --- | --- |
| A complete look for lead and harmony | [Palette and layout example](../../examples/karaoke_designs.py) · [Design tutorial](../../docs/tutorials/karaoke-design.md) | Both voices remain legible during their overlap. |
| Improve colour, font or ruby | [Font and contrast guide](../../docs/guides/fonts-and-preview.md) · [Timed highlights](../../docs/tutorials/lyric-highlights.md) | Sample a half-sung glyph on the actual background. Check the smallest reading and compare a reduced grayscale frame. |
| Fix alternating rows or count-ins | [Orchestration example](../../examples/lyric_orchestration.py) · [Tracks](../../docs/guides/tracks.md) · [Cues](../../docs/guides/text-and-cues.md) · [Paw countdown and character flips](../../docs/examples/README.md#paw-countdown-and-character-flips) | Inspect the third line in a fast left–right–left exchange, including preview, tail, ruby and cue clearance. |
| Choose entry, singing decorations or exit | [Built-in effect catalog](../../docs/guides/karaoke-effects.md#entry-and-exit) | Choose entry and exit independently. For stars, petals or rings emitted by the singing glyph, select a singing decoration and preview its onset and tail. |
| Add movement or particles | [Motion studies](../../docs/tutorials/lyric-studies.md) · [Particle example](../../examples/lyric_particles.py) | Preview short attacks and held notes with the effect at its largest extent. |
| Diagnose a difference between ASS and hook | [Output guide](../../docs/guides/choosing-output.md) · [Troubleshooting](../../docs/guides/troubleshooting.md) | Compare the same singing position in each target renderer. |

## Apply the design to timed lyrics

Examples include their own lyrics so they can run on their own. To reuse a design with a song, apply the layout and effects needed for the requested look to the input Document. Preserve the source text, readings and singing times.

For reusable styling, expose a sequence named `tracks` in an effect file. To prepare tracks and add custom scene objects, expose `build(document) -> Scene` instead. From a source checkout, run the alternating-colour builder with its matching lyric fixture:

```sh
python -m examples.track_colors preview.hook
```

For a standalone libplacebo hook, prepare the Scene in Python and call `scene.export("preview.hook", fps=60)` with the delivery frame rate. See the [CLI contracts](../../docs/guides/cli.md), [output guide](../../docs/guides/choosing-output.md) and [API reference](../../docs/reference/README.md).

For character animation, choose the written glyph as the target. Use `entry_unit="character"` or `exit_unit="character"` on `KaraokeEffects` for independent glyph motion in both body and ruby. Check a long reading across a short base during both transitions.

## Time a count-in to the song

Pass the confirmed song tempo to `prepare_tracks(..., bpm=bpm)` (or the cue binder). For a designed count-in, aim for about three seconds of visible warning before the pickup. Choose a clearly countable number of steps and a step duration of `(60 / bpm) * 2**N` seconds, where N is any integer (e.g. a quarter beat, half beat, beat or two beats). Work backwards from the pickup in complete steps. Built-in presets use their own tempo-based timing when `lead` and `duration` are unset. Use the selected preset’s `resolve_timing(bpm=bpm)` to check the space before each entrance. For `VolumeCue`, three default flashes and the final column fill occupy four beats. Count the flashes against the music and check the last column at the vocal pickup. [Cue timing and overrides](../../docs/guides/text-and-cues.md#choose-the-countdown-order)

Make the remaining time readable from the first frame. Match the timing check to the cue’s visual design:

- **Symbol countdown.** Show the remaining symbols together. When their number communicates the count, keep the outgoing symbol readable until the step boundary and remove it on that boundary. A short bounce can mark an intermediate beat.
- **Sweep or fill.** Advance the colour continuously. Time its leading edge to reach the intended marker or segment end on the musical boundary; the final fill reaches its endpoint at the pickup.

Align the countdown endpoint with the first sung highlight. When pre-roll is short, use the complete steps that fit at the chosen cadence. Keep the cue readable over the footage and clear of lyrics and ruby.

Play the cue at normal speed against the music. For a symbol countdown, compare the number visible immediately before and after a counted boundary. For a sweep, check the edge’s arrival at its target. Inspect the last step and the pickup in both cases.

## Verify the render

Play the exported passage with the intended background and fonts. Inspect the first sung frame, a mid-word sweep, the row handoff and the release. Check countdown and harmony timing where present. Preview each delivery format in its target renderer.
