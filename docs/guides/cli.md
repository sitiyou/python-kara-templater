# Command-line interface

The CLI loads input ASS into a Document and exports a standalone libplacebo hook. Use a
Python Scene script for unrestricted authoring, or Track configuration for
applying reusable styling to imported lyrics.

## Preset styling

```sh
kara-templater input.ass output.hook --after '#33ddff'
```

Use `--before` and `--after` to set the fills on either side of the wipe.
They default to the ASS secondary and primary colors, respectively. --pulse accepts none, char, chars, or syllable. Character
arrival, simultaneous characters, and a shared syllable pulse have different
clocks and pivots. --fade-in-ms/--fade-out-ms control fades;
--lead-ms/--tail-ms extend the display window without altering lyric timing.
Black drop shadows retain the source style's opacity through changes in lyric
color and face opacity in both output formats. Fades apply to the entire line,
including its drop shadow.
Omit --tail-ms for the automatic one-second tail including the fade, with
200 ms of preferred hold when room permits. Pass --tail-ms 0 to request just the required animation time.
Repeat --style to restrict imported styles. --owner selects a stable generation
owner for replacement on subsequent runs.

The preset retains source alignment and event/style margins through a layout
allocator. Lyrics become ordinary Scene objects, with shared fades, pulses and
highlight masks. Whole-scene budgets apply to the generated events.
Fade durations reserve time outside the timed intervals; insufficient time before zero is
an error rather than a silently shortened animation.

Add `--ass` to invoke the [standard ASS compiler](compilation.md). Hook export defaults to 60 fps. Set `--fps` to the delivery frame rate.

## Track configurations

An effect file may export a sequence named tracks:

```python
from kara_templater import CYAN, FadeIn, LyricHighlights, LyricRule, StatePatch, Track

tracks = (
    Track(
        id="main",
        effects=(
            LyricRule("line", "enter", FadeIn(), duration=0.2),
            LyricHighlights.from_timing(StatePatch(fill=CYAN)),
        ),
    ),
)
```

Run `kara-templater input.ass output.hook --effect my_tracks.py`.
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

`--max-bytes` limits the complete Hook file or the generated ASS event bytes.
With `--ass`, `--max-events` also limits the number of generated events and
`--max-active` limits how many can overlap. A budget error leaves the output
path untouched.
Use `python -m kara_templater` when the console entry point is not on PATH.
