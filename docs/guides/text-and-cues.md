# Ruby readings and cues

Control how ruby readings align over body text, add animated count-ins before vocal entries, and map timed placeholder symbols to vector graphics. Covers built-in cues, BPM timing, custom cue factories, and low-level text layout.

## Position and group ruby readings

On horizontal tracks, all ruby readings in a line share one baseline by default (`ruby_alignment="line"`). The lowest reading outline clears the tallest body outline by `ruby_gap` script pixels (default `6`).

To place each reading group relative to its own body ink instead of the tallest glyph on the line, set `ruby_alignment="group"`:

```python
from kara_templater import Track

track = Track(id="main", ruby_alignment="group", ruby_gap=4)
```

Smaller `ruby_gap` values bring readings closer to the body; negative values allow overlap. Clearance is measured from shaped ink plus static hard strokes (and any `reserved_border`) before animation—shadows, glow, and scale pulses can extend into the gap. Because `ruby_gap` uses `PlayRes` script pixels, it scales with the video.

Horizontal ruby follows Aegisub's grouping rules:

- Adjacent annotated syllables join into one reading group.
- Short readings center over their group at natural spacing. On italic faces, the optical center follows the slant of the ink, while outline clearance keeps neighboring readings from colliding.
- Wide readings start at the group's left edge. Bare syllables absorb preceding overhang; if more room is needed, the next group shifts together with its body.
- In code-authored documents (`Document.create`), `|!` starts a separate reading group and `|<` lets a wide reading spill equally left and right. See the [Aegisub furigana tutorial](https://aegisub.org/docs/latest/furigana_karaoke) for background on these rules.

## Add count-in cues to a Track

Insert a cue marker in your timed line and register a matching `CuePreset` in `Track.cues`:

```python
from kara_templater import (
    CueMarker,
    CuePreset,
    Document,
    KaraokeEffects,
    Line,
    Style,
    Track,
    VolumeCue,
    build_lyric_scene,
)

document = Document.create(
    styles=(Style(fontname="DejaVu Sans", fontsize=56, shadow=0),)
)
document.records.append(
    Line(
        start_time=3000,
        end_time=5500,
        text=CueMarker("intro", "count").markup() + r"{\k120}Ready {\k130}now",
    )
)

scene = build_lyric_scene(
    document,
    bpm=120,
    tracks=(
        Track(
            id="main",
            cues={"count": CuePreset(factory=VolumeCue())},
            effects=(KaraokeEffects(),),
        ),
    ),
)
scene.export("count_in.hook")
```

Choose a built-in cue factory based on the visual style you want:

| Factory | Before the lyric starts | At the cue end |
| --- | --- | --- |
| `VolumeCue` | Descending columns pulse together (`flashes=3`), then fill to the highlight color left to right (`count=4`). | All columns clear. |
| `SignalCue` | A row of shapes (`circle`, `square`, `rounded`, `star`, `note8`, `note16`, `notepair`, or a unit-square `VectorPath`) extinguishes step by step. | The last lamp clears. |
| `BarsCue` | A descending bar countdown drops one bar per step. | The last bar clears. |
| `TextCue` | Each step displays its text label (default `("3", "2", "1")`). | The last label clears. |

### Size, shape, and color inheritance

- **Default size**: `VolumeCue` and `SignalCue` default to half (`size_ratio=0.5`) the authored font size at the marker (for example, 40 px for an 80 px font). `BarsCue` and `TextCue` default to the full authored font size (48 px without a host; `BarsCue` width is 1.5× height). Set `height` on `VolumeCue`, `size` on `SignalCue`, or `font_size` on `TextCue` for fixed script pixels.
- **Volume column shape**: `column_width_ratio` sets column width relative to height (default `0.25`); `align` aligns shorter columns to `"center"` (default), `"top"`, or `"bottom"`; `transition` controls flash softness from `0` (hard blink) to `1` (default `0.67`).
- **Lamp details**: `SignalCue` includes a subtle edge highlight that fades with each lamp (`edge_brightness=0` turns it off). Set `spacing` for extra pixels between lamps and `slide=Vec2(...)` to shift each lamp as it fades.
- **Colors and effects**: When your track uses `KaraokeEffects`, `SignalCue` lamps inherit the highlight fill, outline, `SecondaryOutline`, and `glow`. `VolumeCue` columns switch from base paint (`before_fill`, `before_outline`, `secondary_outline`, `base_glow`, `base_material`) to highlight paint (`after_fill`, `after_outline`, `after_secondary_outline`, `glow`, `material`) as each column fills. Leading inline volume columns share the first nonblank singer's horizontal `LyricGradient` ramp. With `zoom_pulse` or `zoom_pulse_scanline`, lamps and columns pulse with the same curve level.
- **Fixed palette**: Pass `CuePreset(colors=PaintPair(...))` to override automatic palette inheritance across tracks.

### Choose countdown direction

For `SignalCue`, choose which lamp stays lit on the final beat before singing begins:

| Factory | All lit | After step 1 | After step 2 | Timing begins |
| --- | --- | --- | --- | --- |
| `SignalCue(direction="left_to_right")` | ● ● ● lyric | · ● ● lyric | · · ● lyric | · · · lyric |
| `SignalCue()` (default `right_to_left`) | ● ● ● lyric | ● ● · lyric | ● · · lyric | · · · lyric |

Here `·` marks the space left by an extinguished lamp. `slide` moves each fading lamp independently of the direction.

## Timing, BPM, and cue placement

A cue finishes at its trigger time (by default, the first timed syllable of the line, after any leading empty `\k` rest). Override the trigger with `CuePreset(trigger=...)` in absolute seconds.

### Explicit timing vs. BPM

- **Explicit seconds**: Pass `lead` and `duration` on `CuePreset`. Setting `lead=duration` ends the cue right on the first syllable. To show all lamps or columns idle before the active countdown begins, set `countdown` in seconds on `SignalCue` or `VolumeCue`—for example, `CuePreset(factory=SignalCue(countdown=2), lead=5, duration=5)` holds all lamps lit for 3 seconds, then counts down over the final 2 seconds. `steps` always increases strictly from `0` to `1`.
- **Automatic BPM timing**: Pass `bpm` to `build_lyric_scene(..., bpm=180)` (or `Document.create(..., bpm=...)`, `bind_cues`, `bind_lyric_cues`). Omitted `lead` follows `duration`:
  - `VolumeCue` budgets 1 beat for the final fill plus `flash_ratio` beats per flash (2.0 s at 120 BPM with the default 3 flashes).
  - Other cues budget 4 beats per step (rounded to milliseconds), halved whenever a step reaches 1800 ms or longer (so 3 steps at 180 BPM span 3.999 s). Nonuniform `steps` divide the total proportionally.
- **Without BPM**: Omitted `lead` and `duration` each default to `1.0` s. Call `preset.resolve_timing(bpm=bpm)` to inspect the exact `(lead, duration)` pair before placing markers.

### Inline vs. independent placement

- **Inline (`placement="inline"`, default)**: Centers on the visible ink of the body glyph at the marker (or the last glyph for an end marker), shifts ruby along with its body, and leaves an automatic `gap` of one eighth of the authored font size (override with `CuePreset(gap=...)`, including `0`). Keep `keep_space=True` (default) so the lyric text does not jump when the cue ends. On vertical tracks, an inline cue advances the column downward.
- **Independent (`placement="independent"`)**: Uses `CuePreset(position=Vec2(...))` in canvas coordinates. On a `Track`, set `CuePreset(line_edge="above")` or `"below"` instead to place the cue cleanly above a bottom row (clearing ruby) or below a top row; row layout reserves the combined height automatically.

See [karaoke_signals.py](../../examples/karaoke_signals.py) for a side-by-side inline `VolumeCue` and independent `SignalCue` track setup.

## Cue marker syntax

Embed a cue marker inside an ASS line as a comment block with the `kara:v1` prefix:

```text
{kara:v1 cue id=count-in preset=bars placement=inline}
```

- `id` and `preset` are required and must be nonempty; `id` must be unique within the line.
- `placement` is optional: `inline` (default) or `independent`.
- Values use POSIX `shlex` quoting, allowing Unicode, spaces, quotes, and `=` without braces, backslashes, or newlines. Use `CueMarker(id, preset, placement=...).markup()` to generate valid markup, or pass Python `CueMarker` objects directly to `bind_cues`/`bind_lyric_cues` without modifying the ASS text.
- A marker's position in the decoded body text sets its anchor offset. Anchors must land inside body text on cluster boundaries—not inside ruby readings or `#` continuation syntax.

> [!NOTE]
> Parse errors on cue markers report the `record_index` and raw character offset in the original ASS `Text` field (including preceding override tags), which differs from the decoded body offset.

## Sing an inline vector symbol

When you want symbols that sweep in time with the lyrics and stay visible afterward (such as breath marks or vertical rhythm guides), give each symbol its own `\k` tag in the body—for example `{\k30}◆{\k30}◆{\k50}歌`—and map that character in `Track.guide_symbols`:

```python
from kara_templater import (
    Document,
    KaraokeEffects,
    Line,
    Style,
    Track,
    Vec2,
    VectorGuide,
    VectorPath,
    build_lyric_scene,
)

document = Document.create(
    styles=(Style(fontname="DejaVu Sans", fontsize=56, shadow=0),)
)
document.records.append(
    Line(start_time=1000, end_time=2500, text=r"{\k30}◆{\k30}◆{\k90}Sing")
)

triangle = VectorPath.polygon(Vec2(0.1, -0.75), Vec2(0.7, -0.4), Vec2(0.1, -0.05))
scene = build_lyric_scene(
    document,
    tracks=(
        Track(
            id="main",
            guide_symbols={"◆": VectorGuide(triangle, advance=0.8)},
            effects=(KaraokeEffects(highlight="utopia_scanline"),),
        ),
    ),
)
scene.export("guide_symbols.hook")
```

Path coordinates and `advance` are multiples of the authored font size at the marker (or `VectorGuide(..., size=...)` in script pixels). `y=0` is the baseline and negative `y` rises above it. The replacement geometry participates in ruby alignment, outline clearance, and both horizontal and vertical sweeps.

To anchor two symbols to the first timed note, give both symbols a `\k0` interval right before it; with the built-in wipe they stay in the waiting color on the onset frame and switch on the next centisecond.

## Build custom cues and low-level text layouts

Any callable matching `(context: CueContext) -> CueContent` works as a `CueFactory`. Return local scene objects along with reserved `width` and `height` (and optional `ink_center_y` for inline vertical alignment; use `CueContent.from_line(line)` to align a measured `LyricLine` automatically). See [scene_cues.py](../../examples/scene_cues.py), [scene_lyric_cues.py](../../examples/scene_lyric_cues.py), and [scene_cue_follow.py](../../examples/scene_cue_follow.py) for complete custom factories and moving anchors.

If you are composing a `Scene` directly without `Track`, bind individual lines with the layout functions:

- `layout_document_text(document, record_index, ...)` + `bind_cues(layout, presets)` for plain text with static inline colors and cues.
- `layout_document_lyrics(document, record_index, ...)` + `bind_lyric_cues(layout, presets)` for body text, positioned ruby, and `#` repeats. `LyricLayout.unit_group(index)` groups a unit's body and readings around the body center so a scale pulse moves them together. See [scene_bilingual.py](../../examples/scene_bilingual.py).
- `TextLayout.characters` gives each cluster's decoded source range, cell bounds, ink bounds, and resolved `FontFace` entries. `range_bounds(start, end)` measures a character span, and `background(start, end, ..., follow=True)` creates a box that follows local text animation (place it in the same parent group, or use a reference across groups).

> [!WARNING]
> Independent-character layout supports Latin, Greek, Cyrillic, CJK, kana, modern Hangul, digits, punctuation, and common lyric marks (keeping combining marks with their base). Joining scripts, bidirectional control characters, emoji sequences, and archaic Hangul jamo raise `LayoutCapabilityError`.

## Next steps

- [Lay out vocal tracks](tracks.md)
- [Choose and register fonts](fonts.md)
- [Built-in karaoke effects](karaoke-effects.md)
- [Lyric cues API reference](../reference/cues.md)
