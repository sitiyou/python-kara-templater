# Guides overview

Task-focused guides walk through importing timed lyrics, styling karaoke effects, and running the command line. Start with the minimal template below, then pick the topic you need.

## Start from a timed ASS file

Load a timed ASS file, attach a `Track` for the lead vocal, and export a standalone Hook. Run this from a repository checkout to try the sample lyrics, or pass your own timed `.ass` file.

```python
from kara_templater import Document, KaraokeEffects, Track, build_lyric_scene

lyrics = Document.load("examples/karaoke.ass")
lead = Track(id="lead", effects=(KaraokeEffects(),))
scene = build_lyric_scene(lyrics, tracks=(lead,))
scene.export("karaoke.hook")
```

A `Document` holds the timed lyrics and metadata. Each `Track` selects a vocal stream and defines how its lines look and move. `build_lyric_scene` turns those tracks into a `Scene` that you can export as a Hook or standard ASS.

To add harmonies or translations, create another `Track` with a source filter and choose where each stream sits on screen.

## Lyrics and layout

- [Import timed lyrics](documents.md) — load ASS files, inspect lyric timing, and see which timing and ruby tags are supported.
- [Lay out vocal tracks](tracks.md) — filter vocal streams, position rows or columns, and control preview and tail windows.
- [Ruby readings and cues](text-and-cues.md) — attach readings and timed count-in cues to lyric ranges.
- [Choose and register fonts](fonts.md) — pick legible typefaces, enable proportional kana spacing, and register font files with `load_font`.

## Effects

- [Built-in karaoke effects](karaoke-effects.md) — configure line entry, highlight wipes, pulses, and exit presets.
- [Colour and materials](materials.md) — paint fills, outlines, glows, gradients, and custom WGSL materials.
- [Animation and timing](animation.md) — schedule tweens, curves, and custom GPU motion on lines, syllables, or characters.
- [Scene objects and groups](objects.md) — add standalone text, paths, and grouped layers with their own timelines.
- [Shapes, clips and masks](geometry.md) — draw vector paths, apply rectangle or vector clips, and add 3D extrusion.
- [Particles, copies and echoes](particles.md) — emit sparkles or petals along the highlight front and build layered echoes.

## Tools

- [Command line](cli.md) — export a Hook or ASS file directly from the terminal using presets, `tracks`, or a `build` function.

## Next steps

- [Core concepts](../concepts.md)
- [Tutorials overview](../tutorials/README.md)
- [Choose an output](../output/README.md)
- [API reference](../reference/README.md)
