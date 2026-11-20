# Documentation

Start with timed lyrics or an empty scene, design an effect in Python, then
[choose an ASS subtitle or a standalone hook](guides/choosing-output.md).

## Write custom effects

1. [Install and export your first scene](getting-started.md).
2. [Write a reusable custom animation](tutorials/custom-animation.md).
3. Learn [objects and coordinates](guides/objects.md) and [animation and timing](guides/animation.md).
4. Explore the [effect gallery](examples/README.md) and adapt its source.
5. Look up types, parameters, and methods in the [API reference](reference/README.md).

## Style existing lyrics

1. Read [Documents and lyrics](guides/documents.md) for input selection and timing.
2. Start with the [recommended main-vocal recipe](guides/karaoke-effects.md#recommended-main-vocal). Compare [wipe, pulse, and instant recolor](guides/karaoke-effects.md#choose-the-singing-motion), or configure [Tracks](guides/tracks.md).
   The [lyric highlight tutorial](tutorials/lyric-highlights.md) provides a complete fixed input.
   Choose row geometry and accents in [Design a karaoke layout](tutorials/karaoke-design.md).
3. Choose the [countdown order](guides/text-and-cues.md#choose-the-countdown-order), or [animate a cursor through a phrase](guides/animation.md#keep-a-cursor-moving-through-a-phrase).
4. Choose [compact ASS, compiled ASS or a hook](guides/choosing-output.md). The [CLI](guides/cli.md) takes ASS input and writes ASS output.

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
