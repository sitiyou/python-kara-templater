# Command line

Turn timed ASS lyrics into karaoke effects from the terminal, then export a playback shader or a standard ASS subtitle. Use built-in preset flags for quick styling, or pass a Python effect file for reusable tracks and custom scenes.

## Export with preset options

Run `kara-templater` with an input `.ass` file and an output path. If the command is not on your `PATH`, run `python -m kara_templater` instead.

```sh
kara-templater input.ass output.hook --after '#33ddff'
```

The built-in preset supplies its own default font, colors, alignment, and margins rather than copying source ASS styling. You can customize colors, timing windows, and motion with flags:

| Flag | Default | Effect |
| --- | --- | --- |
| `--before '#RRGGBB'` | preset color | Fill color before the karaoke wipe. |
| `--after '#RRGGBB'` | preset color | Fill color after the karaoke wipe. |
| `--pulse MODE` | `none` | Scale pulse mode: `none`, `char` (pulse each character as the wipe reaches it), `chars` (pulse characters together on individual pivots), or `syllable` (pulse the whole syllable). |
| `--fade-in-ms MS` | `0` | Fade-in duration in milliseconds for the whole line, including its shadow. |
| `--fade-out-ms MS` | `0` | Fade-out duration in milliseconds for the whole line, including its shadow. |
| `--lead-ms MS` | `0` | Extend display before each timed line without shifting lyric timing. |
| `--tail-ms MS` | automatic | Override display time after timing ends. Omit for the automatic 1 s tail (including fade-out, preferring 200 ms of hold); pass `0` for only the required animation time. |
| `--style NAME` | all styles | Import only lines matching this source style. Repeat to select multiple styles. |
| `--owner NAME` | `default` | Stable tag used when replacing previously generated ASS events on re-runs. |

Fade durations reserve time outside the timed lyric span. If a fade-in needs room before time zero, the CLI stops with an error rather than silently shortening the animation. See [Import timed lyrics](documents.md) for supported `\k` timing and ruby syntax.

## Reuse Track configurations

For projects that need custom layout, multiple vocal streams, or richer effects, save a `tracks` tuple in a Python file and pass it with `--effect`.

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

```sh
kara-templater input.ass output.hook --effect my_tracks.py
```

The CLI builds one `Scene` from those `Track` declarations using the same pipeline as `build_lyric_scene`. Configure source selection, display timing, colors, and animations inside `tracks`; the CLI rejects preset and import flags (`--before`, `--after`, `--pulse`, `--fade-in-ms`, `--fade-out-ms`, `--lead-ms`, `--tail-ms`, and `--style`) when combined with `--effect`. You can still pass `--owner`.

## Build a custom Scene

When you need full `Scene` control—such as custom background shapes, extra layers, or direct record handling—export a `build(document) -> Scene` function from your effect file instead of `tracks`.

```python
from kara_templater import Document, KaraokeEffects, Scene, Track, build_lyric_scene


def build(document: Document) -> Scene:
    lead = Track(id="lead", effects=(KaraokeEffects(),))
    return build_lyric_scene(document, tracks=(lead,), owner="custom")
```

```sh
kara-templater input.ass output.hook --effect my_scene.py
```

Export either `tracks` or `build`, not both. Because `build` controls input selection, timing, styling, and `owner`, the CLI also rejects `--owner` alongside the preset flags.

## Choose output format and budgets

By default, the CLI packages the shader and textures as a `.hook` for mpv or FFmpeg at 60 fps. Pass `--fps` (`1`–`240`) to match your delivery frame rate, or pass `--ass` to compile standard ASS instead.

```sh
kara-templater input.ass output.hook --fps 30
kara-templater input.ass output.ass --ass
```

For real-time browser preview of a scene built in Python, see [Preview and export](../output/README.md). With `--ass`, the CLI prints the generated event count, peak overlapping events, output size in bytes, and any compiler diagnostics.

| Flag | Applies to | Default | Purpose |
| --- | --- | --- | --- |
| `--fps N` | Hook | `60` | Output frame rate (`1`–`240`). |
| `--max-bytes N` | Hook and `--ass` | unlimited (Hook) / 10 MiB (ASS) | Limit the complete Hook file or compiled ASS output in bytes. |
| `--max-events N` | `--ass` only | `10,000` | Limit generated ASS events. |
| `--max-active N` | `--ass` only | `1,000` | Limit simultaneously active ASS events. |

> [!NOTE]
> The CLI defaults `--max-events` to `10,000`, whereas Python `AssBudget` defaults to `25,000`. Passing `--max-events` or `--max-active` without `--ass` raises an error. Whenever a budget check fails, the existing output file is left untouched.

## Next steps

- [Preview and export](../output/README.md)
- [Play and render a Hook](../output/hook.md)
- [Export standard ASS](../output/ass.md)
- [Lay out vocal tracks](tracks.md)
