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
Omit --tail-ms for the automatic one-second tail including the fade, with
200 ms of preferred hold when room permits. Pass --tail-ms 0 to request just the required animation time.
Repeat --style to restrict imported styles. --owner selects a stable generation
owner for replacement on subsequent runs.

The preset retains source alignment and event/style margins through a layout
allocator. Lyrics become ordinary Scene objects, with shared fades, pulses and
highlight masks. Whole-scene budgets apply to the resulting sampled output.
Fade durations reserve time outside singing; insufficient time before zero is
an error rather than a silently shortened animation.

--raster explicitly chooses coverage composition for the preset;
--raster-color-error sets its spatial color tolerance in 0..255 before ASS
transforms. This is not a final YUV420 video error bound. Script effects declare
their own material strategy and budget settings instead of using these flags.

## Track configurations

An effect file may export a sequence named tracks:

```python
from kara_templater import CYAN, FadeIn, LyricRule, LyricSweep, Track

tracks = (
    Track(
        id="main",
        effects=(
            LyricRule("line", "enter", FadeIn(), duration=0.2),
            LyricSweep(fill=CYAN, width=0),
        ),
    ),
)
```

Run `kara-templater input.ass output.ass --effect my_tracks.py`.
Configure selection, layout, preview/tail, colors and animations in the Track
declarations. Each Track is an independent lyric stream, with layout expressed
by its allocator. The CLI binds these declarations into one Scene and invokes
the same compiler as the builder entry point.

## Scene builders

Alternatively, export `build(document) -> Scene` from the effect file. It receives
the parsed Document and can bind input records, prepare Tracks, and add custom
objects. Return the complete Scene to compile. Export either build or tracks,
not both. Input selection, display timing, and material choices for a builder
belong in that function; the CLI rejects conflicting import/raster flags.
Scene builders also choose their owner inside the function; --owner applies to
preset and Track inputs.

--max-events, --max-bytes, and --max-active constrain final Scene output. Budget
or callback errors report source notes and do not save a partial output file.
Use `python -m kara_templater` when the console entry point is not on PATH.
