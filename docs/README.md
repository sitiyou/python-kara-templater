# Documentation index

| Resource | Where to go |
| --- | --- |
| First export | [Getting started](getting-started.md) walks through installation, export and playback. |
| Template authoring | The [template skill](../skills/kara-templater/SKILL.md) covers choosing a working example, styling timed lyrics and checking the rendered result. |
| Tutorials | [Custom animation](tutorials/custom-animation.md), [timed highlights](tutorials/lyric-highlights.md), [karaoke layout](tutorials/karaoke-design.md) and [lyric motion studies](tutorials/lyric-studies.md) |
| Examples | The [effect gallery](examples/README.md) pairs rendered previews with runnable source. |
| Export formats | [Choosing an output](guides/choosing-output.md) compares compact ASS, compiled ASS and standalone hooks. |

## Task guides

| Topic | What you can do |
| --- | --- |
| [Documents and lyrics](guides/documents.md) | Load ASS, preserve source records, read karaoke timing and custom markers |
| [Objects and coordinates](guides/objects.md) | Create, group, copy, position, and transform visual objects |
| [Animation and timing](guides/animation.md) | Compose animations, write callbacks, schedule events, and resolve clocks |
| [Built-in karaoke effects](guides/karaoke-effects.md) | Choose entry, singing, exit, particles and outline flash |
| [Tracks](guides/tracks.md) | Select source lyrics and configure text, highlights, layout, and animations |
| [Text, ruby, and cues](guides/text-and-cues.md) | Shape text, bind readings, place inline or independent cue objects |
| [Geometry and masks](guides/geometry.md) | Work with paths, outlines, boolean operations, writing, and morphing |
| [Colors and materials](guides/materials.md) | Add soft sweeps, gradients, blur, scoped opacity, and explicit raster output |
| [Particles and references](guides/particles.md) | Emit deterministic particles, make echoes, and follow world-space objects |
| [ASS compilation and performance](guides/compilation.md) | Choose output semantics, inspect reports, and control resource budgets |
| [Fonts and preview](guides/fonts-and-preview.md) | Choose typefaces for main lyrics, harmony and ruby; register fonts and preview the result |
| [Standalone hook](guides/gpu-rendering.md) | Render with FFmpeg or seek in mpv |
| [CLI](guides/cli.md) | Export presets, Track configurations, and custom Scenes |
| [Troubleshooting](guides/troubleshooting.md) | Diagnose missing glyphs, input restrictions, animation conflicts, and costs |

## Reference and maintenance

- [API reference](reference/README.md) covers the final public exports and members.
- [ASS and playback](ass-and-playback.md) explains renderer and output limits.
- [Contributing](contributing/README.md) covers setup, architecture, checks, and releases.

Gallery captions identify the rendering path. Repository examples and tools require a
source checkout. Standalone tutorial scripts use the installed package.
