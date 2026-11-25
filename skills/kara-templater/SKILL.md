---
name: kara-templater
description: Design or revise karaoke templates with kara-templater, including typography, ruby, vocal tracks, countdowns, sweep colours and lyric effects. Verify the result in the target renderer.
---

# Design a karaoke template

Read the lyric phrasing and mood, listen for rhythmic accents and section changes, and inspect the footage's composition, palette, and cuts. Pick a coherent visual direction for this song and carry it through the type, placement, highlight colour, and motion. Let a salient lyric, musical accent, or visual transition motivate a change of treatment. Check that the timing guide and readings remain easy to follow against the footage.

Use the default two-row karaoke layout that alternates left and right. Change the layout only when the user explicitly asks for it. Inherit library defaults and pass optional arguments only for deliberate design choices. Preserve the supplied lyric text, readings and timing.

Follow the project's workflow when it fits the task. The CLI applies presets or effect files to timed ASS. Scripts and applications can build and export a Scene directly. [CLI guide](../../docs/guides/cli.md) · [Scene example](../../docs/getting-started.md#write-your-first-python-template)

## Read the guide for the change

When exploring a design, start with the [example index by visual goal](../../docs/examples/README.md#find-an-example-by-its-visual-goal). Use the preview and linked source to compare visual mechanisms. Use the catalog for the complete built-in options.

| Design task | Start here |
| --- | --- |
| Font, ruby, spacing and contrast | [Karaoke design](../../docs/tutorials/karaoke-design.md) and [fonts](../../docs/guides/fonts.md) |
| Vocal tracks and alternating rows | [Tracks](../../docs/guides/tracks.md) and [orchestration example](../../examples/lyric_orchestration.py) |
| Sweep colours, entry, exit and timing effects | [Timed highlights](../../docs/tutorials/lyric-highlights.md) and [effect catalog](../../docs/guides/karaoke-effects.md) |
| Count-ins | [Add a rhythmic count-in](../../docs/tutorials/karaoke-design.md#add-a-rhythmic-count-in) |
| Custom motion or particles | [Motion studies](../../docs/tutorials/lyric-studies.md) and [effect gallery](../../docs/examples/README.md) |
| Renderer constraints | [Output formats](../../docs/output/README.md) and [troubleshooting](../../docs/output/troubleshooting.md) |

## Verify on representative lyrics

Use a passage with a held vowel, a quick row change and ruby when present. Include overlapping voices for multi-voice songs. Use intended footage if available. A neutral background suffices for checking standalone Hook layout, timing and font coverage.

Play the rendered passage at the target frame rate. Inspect the first highlight, a mid-word sweep, a row handoff and the release. Check the longest line and densest reading before exporting the whole song.
