# Overview

Build animated karaoke scenes from timed lyrics in Python, write custom materials in WGSL, and preview the result live in your browser.

## What kara-templater does

`kara-templater` takes timed lyrics — typically an ASS file with `\k` syllable durations, optional ruby readings, and count-in markers — and turns them into animated karaoke overlays using Python. It measures actual font outlines with FreeType and HarfBuzz so wipes, ruby alignment, outlines, and decorations line up accurately with the rendered lettering.

Naga validates WGSL material functions and translates them to GLSL. The shader can run in a WebGL 2 preview or be packaged with its textures as a libplacebo `.hook` for mpv and FFmpeg. Standard ASS export supports conventional subtitle players.

## How a template fits together

Follow the lyrics from `Document` through `Track` and `Scene` to real-time preview or export.

| Stage | Primary API | Role |
| --- | --- | --- |
| Lyrics & canvas | `Document`, `Style`, `Line` | Stores script resolution (`PlayRes`), font styles, and timed lyric lines loaded from ASS or built in Python. |
| Vocal streams | `Track`, `KaraokeRows`, `Layout`, `KaraokeEffects`, `LyricRule` | Selects lines for each vocal part, arranges rows or columns, schedules display padding, and attaches visual effects. |
| Composition | `build_lyric_scene`, `Scene`, `TextObject`, `PathObject`, `ObjectGroup` | Holds the measured, positioned lyric lines alongside any custom shapes, backgrounds, or animations. |
| Preview and export | `Scene.preview`, `Scene.export_resources`, `Scene.export`, `Scene.ass.compile` | Opens a browser preview, writes shader resources or a playback package, or compiles standard ASS. |

Read [Core concepts](concepts.md) for the exact time units, coordinate spaces, and lifetime rules shared across all four stages.

## Find the right guide

### Start here

- [Quickstart](getting-started.md) — Install `kara-templater`, run a preset, write your first Python template, and preview it in a browser.
- [Core concepts](concepts.md) — Learn the `Document` → `Track` → `Scene` model, time units, coordinates, lifetimes, and output choices.
- [Example scripts](examples/README.md) — Browse runnable scripts and previews organized by visual goal.

### Tutorials

- [Tutorials overview](tutorials/README.md) — Pick a guided walkthrough from layout to custom motion.
- [Design a song layout](tutorials/karaoke-design.md) — Style lead and harmony vocals, spacing, and whole-song palettes.
- [Animate the highlight](tutorials/lyric-highlights.md) — React to measured syllable sweeps with arrival-triggered motion.
- [Write a custom animation](tutorials/custom-animation.md) — Build reusable motion with `Transform`, timelines, and rules.
- [Effect recipes](tutorials/effect-recipes.md) — Adapt self-contained entrance, typing, focus, and breakup recipes.
- [Motion studies](tutorials/lyric-studies.md) — Compare eight timing, echo, particle, and ornament studies side by side.

### Guides

- **Lyrics and layout**: [Guides overview](guides/README.md) · [Import timed lyrics](guides/documents.md) · [Lay out vocal tracks](guides/tracks.md) · [Ruby readings and cues](guides/text-and-cues.md) · [Choose and register fonts](guides/fonts.md)
- **Effects and scene authoring**: [Built-in karaoke effects](guides/karaoke-effects.md) · [Colour and materials](guides/materials.md) · [Animation and timing](guides/animation.md) · [Scene objects and groups](guides/objects.md) · [Shapes, clips and masks](guides/geometry.md) · [Particles, copies and echoes](guides/particles.md)
- **Tools**: [Command line](guides/cli.md)

### Output and reference

- **Playback and export**: [Preview and export](output/README.md) · [Play and render a Hook](output/hook.md) · [Export standard ASS](output/ass.md) · [Troubleshooting](output/troubleshooting.md)
- **Reference and development**: [API reference](reference/README.md) · [Contributing](contributing/README.md) · [Template authoring skill](../skills/kara-templater/SKILL.md)

## Next steps

- [Quickstart](getting-started.md) — Export your first scene and open it in a browser.
- [Core concepts](concepts.md) — Understand time units, coordinates, and lifetimes before authoring custom templates.
- [Example scripts](examples/README.md) — Find a runnable script close to the look you want.
- [Design a song layout](tutorials/karaoke-design.md) — Build a complete multi-vocal karaoke template.
