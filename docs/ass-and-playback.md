# ASS output and playback

The ASS exporter resolves supported scene objects, native animations and input cue
markers during generation; the player needs no
kara-templater plugin or patched libass. Use a player with ASS support and provide
the selected fonts.

## What the format can express

Text, vector drawings, transforms, clips, alpha, color, blur, and multiple timed
events provide the building blocks. The compiler supports static text and paths, native movement, eligible transforms and
hard wipes. Effects that require per-frame events, spatial color bands or raster
coverage groups raise `SceneCompileError` during export. Use the hook exporter for
glyph gradients, feathered wipes and procedural particle motion. See
[Choose an output](guides/choosing-output.md).

Preserving an ASS record does not mean every override can become an editable
Scene object. NativeEvent preserves already-lowered behavior; text/lyric
frontends reject unsupported editable semantics with source context.

## Rendering environment matters

Font files, fallback, shaping, PlayRes, output dimensions, timestamp, color matrix,
and subtitle/video scaling all affect pixels. Keep those fixed for comparisons.
load_font registers metrics resources in Python; configure playback fonts
separately. A matching family name is insufficient proof of identical font bytes.

Use the exported ASS and the intended player to judge full-size playback.
Material pixel comparisons need RGB or full-resolution chroma composition.
YUV420 can introduce edges between encoded pixel rectangles.

## Renderer differences

The [libass differences guide](https://github.com/libass/libass/wiki/Differences-between-Libass-and-VSFilters)
describes differences from VSFilter-family renderers, including outlines and
transforms, font/locale behavior, fractional sizes, border styles, and color
handling. These differences warrant testing the intended renderer with the
actual fonts and video settings. Standard syntax does not guarantee identical
pixels across implementations.

For mpv, the [ASS override option](https://mpv.io/manual/stable/#options-sub-ass-override)
and [VSFilter color compatibility option](https://mpv.io/manual/stable/#options-sub-ass-vsfilter-color-compat)
allow an RGB-oriented script to avoid user-style and compatibility color changes:

```sh
mpv video.mkv --sub-file=effect.ass --sub-ass-override=no --sub-ass-vsfilter-color-compat=no
```

This is a reproduction configuration, not a claim that every mpv/VSFilter
environment has passed project pixel tests. Test font discovery, scaling,
entrance/exit, repeated highlights, continuous playback, and seeking in your
delivery environment. Platform/package checks and renderer visual checks prove
different things; contributor instructions explain the relevant verification.

See [fonts and preview](guides/fonts-and-preview.md),
[compilation](guides/compilation.md), and [troubleshooting](guides/troubleshooting.md).

For continuous shader gradients, distribute a standalone libplacebo hook alongside
the standard ASS. FFmpeg can render the hook directly. See
[GPU rendering](guides/gpu-rendering.md).
