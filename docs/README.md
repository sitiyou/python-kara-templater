# Documentation

Create custom effects with Python and export standard ASS. Choose a reading path,
then use the task guides and API reference as you work.

## Write custom effects

1. [Install and generate your first ASS](getting-started.md).
2. [Write a reusable custom animation](tutorials/custom-animation.md).
3. Learn [objects and coordinates](guides/objects.md) and [animation and timing](guides/animation.md).
4. Explore the [effect gallery](examples/README.md) and adapt its source.
5. Look up types, parameters, and methods in the [API reference](reference/README.md).

## Style existing lyrics

1. Read [Documents and lyrics](guides/documents.md) for input selection and timing.
2. Configure [Tracks](guides/tracks.md) or execute [Python templates](guides/templates.md).
   The [lyric highlight tutorial](tutorials/lyric-highlights.md) provides a complete fixed input.
3. Add [custom text, ruby, and cues](guides/text-and-cues.md) or other Scene objects.
4. Export using the [CLI](guides/cli.md) or compile in Python.

## Task guides

| Topic | What you can do |
| --- | --- |
| [Documents and lyrics](guides/documents.md) | Load ASS, preserve source records, read karaoke timing and custom markers |
| [Objects and coordinates](guides/objects.md) | Create, group, copy, position, and transform visual objects |
| [Animation and timing](guides/animation.md) | Compose animations, write callbacks, schedule events, and resolve clocks |
| [Tracks](guides/tracks.md) | Select source lyrics and configure text, highlights, layout, and animations |
| [Text, ruby, and cues](guides/text-and-cues.md) | Shape text, bind readings, place inline or independent cue objects |
| [Geometry and masks](guides/geometry.md) | Work with paths, outlines, boolean operations, writing, and morphing |
| [Colors and materials](guides/materials.md) | Add soft sweeps, gradients, blur, scoped opacity, and explicit raster output |
| [Particles and references](guides/particles.md) | Emit deterministic particles, make echoes, and follow world-space objects |
| [Compilation and performance](guides/compilation.md) | Choose output semantics, inspect reports, and control resource budgets |
| [Fonts and preview](guides/fonts-and-preview.md) | Register fonts, render saved ASS, and reproduce an example |
| [CLI](guides/cli.md) | Export presets, Track configurations, custom Scenes, and templates |
| [Templates](guides/templates.md) | Use the preserved ASS Python-template frontend explicitly |
| [Troubleshooting](guides/troubleshooting.md) | Diagnose missing glyphs, input restrictions, animation conflicts, and costs |

## Reference and maintenance

- [API reference](reference/README.md) covers the final public exports and members.
- [ASS and playback](ass-and-playback.md) explains renderer and output limits.
- [Contributing](contributing/README.md) covers setup, architecture, checks, and releases.

All user examples produce ASS. Gallery GIFs are previews rendered from those ASS
files. The repository's `examples` and `tools` modules require a source checkout;
standalone tutorial scripts use only the installed `kara_templater` package.
