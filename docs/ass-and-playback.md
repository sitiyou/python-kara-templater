# ASS output and playback

All runtime output is standard ASS. Python objects, animation callbacks, input
cue markers, and template helpers run during generation; the player needs no
kara-templater plugin or patched libass. Use a player with ASS support and provide
the selected fonts.

## What the format can express

Text, vector drawings, transforms, clips, alpha, color, blur, and multiple timed
events provide the building blocks. Curves, geometry changes, gradients, and
particles are compiled into those primitives. Scene offers explicit budgets and
reports because complex effects can create large files or many active events.

ASS has no general-purpose shader, arbitrary blend modes, video textures, or
3D camera. Raster/coverage exits approximate richer composition with standard
ASS rectangles; their event and playback costs remain real. Morphing requires
corresponding contours, writing requires authored strokes, and custom callback
sampling does not establish a continuous error bound.

Preserving an ASS record does not mean every override can become an editable
Scene object. NativeEvent preserves already-lowered behavior; text/lyric
frontends reject unsupported editable semantics with source context.

## Rendering environment matters

Font files, fallback, shaping, PlayRes, output dimensions, timestamp, color matrix,
and subtitle/video scaling all affect pixels. Keep those fixed for comparisons.
load_font registers metrics resources in Python; configure playback fonts
separately. A matching family name is insufficient proof of identical font bytes.

The gallery is rendered with FFmpeg/libass, repository fonts, and recorded
settings. Its reduced GIFs illustrate motion; use the full saved ASS when judging
the intended player. Material pixel comparisons need RGB or full-resolution
chroma composition. YUV420 can introduce edges between encoded pixel rectangles.

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

GPU-enhanced output is a separate opt-in workflow: ordinary players use its ASS
fallback and ignore the private effect comments. The dedicated renderer reads
those comments and produces video with continuous shader gradients. See
[GPU-enhanced ASS](guides/gpu-rendering.md) for supported features and file costs.
