# Command-line interface

The CLI loads input ASS into a Document and saves compiled standard ASS. Use a
Python Scene script for unrestricted authoring, or Track configuration for
applying reusable styling to imported lyrics.

## Preset styling

```sh
kara-templater input.ass output.ass --after '#33ddff' --pulse char
```

The source secondary color is unsung and primary color sung unless overridden
by --before/--after. --pulse accepts none, char, chars, or syllable. Character
arrival, simultaneous characters, and a shared syllable pulse have different
clocks and pivots. --fade-in-ms/--fade-out-ms control fades;
--lead-ms/--tail-ms extend the display window without rewriting singing time.
Repeat --style to restrict imported styles. --owner selects a stable generation
owner for replacement on subsequent runs.

## Track configurations

An effect file may export a sequence named tracks:

```python
from kara_templater import CYAN, Body, LineMatch, Overlay, PaintStyle, Track

tracks = (
    Track(source=LineMatch(), body=Body(), overlay=Overlay(style=PaintStyle(fill=CYAN))),
)
```

Run `kara-templater input.ass output.ass --effect my_tracks.py`.
TrackGroup values are also accepted. Configure colors, pulses, and fades inside
the file rather than combining the preset appearance flags with --effect.
The CLI prepares Track configurations in native mode, retaining ordinary source
style semantics. --raster explicitly enables the native Track material-raster
exit; --raster-color-error bounds its spatial color approximation in 0..255.

## Scene builders

Alternatively, export `build(document) -> Scene` from the effect file. It receives
the parsed Document and can bind input records, prepare Tracks, and add custom
objects. Return the complete Scene to compile. Export either build or tracks,
not both. Input selection, display timing, and material choices for a builder
belong in that function; the CLI rejects conflicting import/raster flags.
Scene builders also choose their owner inside the function; --owner applies to
preset, Track, and template inputs.

--max-events, --max-bytes, and --max-active constrain final Scene output. Budget
or callback errors report source notes and do not save a partial output file.
Use `python -m kara_templater` when the console entry point is not on PATH.

## ASS Python templates

```sh
kara-templater input.ass output.ass --templates
```

This explicitly runs the preserved template frontend. --video-size WIDTH HEIGHT
is its aspect correction option and requires --templates. Template execution
cannot be mixed with effect/preset flags. See [templates](templates.md) for its
input conventions and Python execution model.
