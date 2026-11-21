---
name: kara-templater
description: Design and verify Python karaoke templates with kara-templater for ASS and libplacebo hook output. Use for typography, ruby, vocal tracks, countdowns, highlight palettes, particles and animated lyric effects.
---

# Design a karaoke template

For a first standalone export, follow [Getting started](../../docs/getting-started.md).

Start with a short passage of timed lyrics from the song, a representative background and the intended canvas and frame rate. Select a passage with a held vowel, a quick row change and ruby. Include overlapping voices if the song has them.

## Find the closest working example

Choose a row for the requested change. Inspect the rendered example and its source, then use the linked guide for the controls involved. For a broad visual brief, start with the [effect gallery](../../docs/examples/README.md).

| Request | Starting point | Check on the song |
| --- | --- | --- |
| A complete look for lead and harmony | [Palette and layout example](../../examples/karaoke_designs.py) · [Design tutorial](../../docs/tutorials/karaoke-design.md) | Both voices remain legible during their overlap. |
| Improve colour, font or ruby | [Font and contrast guide](../../docs/guides/fonts-and-preview.md) · [Timed highlights](../../docs/tutorials/lyric-highlights.md) | Sample a half-sung glyph on the actual background. Check the smallest reading and compare a reduced grayscale frame. |
| Fix alternating rows or count-ins | [Orchestration example](../../examples/lyric_orchestration.py) · [Tracks](../../docs/guides/tracks.md) · [Cues](../../docs/guides/text-and-cues.md) | Inspect the third line in a fast left–right–left exchange, including preview, tail, ruby and cue clearance. |
| Add movement or particles | [Motion studies](../../docs/tutorials/lyric-studies.md) · [Particle example](../../examples/lyric_particles.py) | Preview short attacks and held notes with the effect at its largest extent. |
| Diagnose a difference between ASS and hook | [Output guide](../../docs/guides/choosing-output.md) · [Troubleshooting](../../docs/guides/troubleshooting.md) | Compare the same singing position in each target renderer. |

## Apply the design to timed lyrics

Examples include their own lyrics so they can run on their own. To reuse a design with a song, take its Track layout and effects and apply them to the input Document. Preserve the source text, readings and singing times.

For reusable styling, expose a sequence named `tracks` in an effect file. To prepare tracks and add custom scene objects, expose `build(document) -> Scene` instead. From a source checkout, run the alternating-colour builder with its matching lyric fixture:

```sh
python -m examples.track_colors preview.ass
```

For a standalone libplacebo hook, prepare the Scene in Python and call `scene.export_hook("preview.hook", fps=60)` with the delivery frame rate. See the [CLI contracts](../../docs/guides/cli.md), [output guide](../../docs/guides/choosing-output.md) and [API reference](../../docs/reference/README.md).

## Verify the render

Play the exported passage with the intended background and fonts. Inspect the first sung frame, a mid-word sweep, the row handoff and the release. Check countdown and harmony timing where present. Preview each delivery format in its target renderer.
