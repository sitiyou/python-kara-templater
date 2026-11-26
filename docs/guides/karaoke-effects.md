# Built-in karaoke effects

Add timed colour wipes, entrances, exits, pulses and particle decorations to a vocal track in one declaration. Use this guide when built-in presets cover the look you want without writing custom animations.

## Start with a karaoke wipe

Attach `KaraokeEffects()` or `KaraokeEffects.duotone()` to `Track.effects` to animate an entire vocal track from its timed lyrics. You do not need to schedule individual words or characters.

```python
from kara_templater import (
    Document,
    KaraokeEffects,
    Line,
    Style,
    Track,
    build_lyric_scene,
)

document = Document.create(
    width=640,
    height=360,
    styles=(Style(fontname="DejaVu Sans", fontsize=56, bold=True, outline=2, shadow=0),),
)
document.records.extend((
    Line(start_time=1000, end_time=3000, text=r"{\k30}We {\k50}sing {\k120}tonight"),
    Line(start_time=3200, end_time=5000, text=r"{\k45}In {\k35}warm {\k100}light"),
))

scene = build_lyric_scene(
    document,
    tracks=(Track(id="main", effects=(KaraokeEffects.duotone(),)),),
)
scene.export("karaoke.hook")
```

`KaraokeEffects()` gives you the catalog defaults: a 0.30 s fade at each end of the line, a white-to-coral colour wipe, and a subtle `utopia` scale pulse on each syllable.

`KaraokeEffects.duotone()` draws a steady wipe (`highlight="none"`) that transitions both fill and outline together. It picks a contrasting outline for each fill automatically, or uses any `before_outline` and `after_outline` colours you pass.

By default, `duotone()` softens the wipe edge across one sixth of each glyph's font size (`Glyph.font_size / 6` — 12 px on a 72 px lyric, 6 px on a 36 px reading). Pass a fixed pixel width such as `feather=12`, a narrower ratio such as `feather=Glyph.font_size / 8`, or `feather=0` for a crisp edge.

![Four libplacebo crops compare fixed and proportional edges on 36 and 48 px readings.](../examples/assets/relative-ruby.png)

From left to right, the first pair shows a 36 px reading with a fixed 12 px edge and the automatic 6 px edge. The second pair shows a 48 px reading with 12 px and 8 px edges while the 72 px body keeps its 12 px edge.

## Share a palette across tracks

Use `KaraokeTheme` to keep lead vocals, harmonies, count-in cues and following particles on one palette. Pass a shared theme to `build_lyric_scene`, override individual roles on a `Track`, or set a colour directly on an effect for highest priority.

```python
from kara_templater import CYAN, Color, KaraokeEffects, KaraokeTheme, Track

song_theme = KaraokeTheme(after_fill=Color.hex("#FF964A"))
harmony_track = Track(
    id="harmony",
    theme=KaraokeTheme(after_fill=CYAN),
    effects=(KaraokeEffects.duotone(),),
)
```

`KaraokeTheme` defines five RGB roles: `before_fill`, `after_fill`, `before_outline`, `after_outline` and `shine` (used for scanlines, stroke flashes, echoes and glints). Ordinary `KaraokeEffects()` keeps source outlines until you supply outline roles; `duotone()` derives contrasting outlines for both sides.

A `Track` without a catalog effect keeps its source ASS paint. Adding `KaraokeEffects` takes ownership of both sides of the colour transition, including text with inline ASS colour overrides. For per-word colours, use `LyricHighlights.from_timing` with `segment_colors` or a custom material as shown in [Colour and materials](materials.md).

![Two main-vocal palettes with the same violet harmony over light and dark video.](../examples/assets/track-themes.png)

You can also layer outer rims and halos directly on `KaraokeEffects` or `LyricHighlights.from_timing` using `secondary_outline`, `after_secondary_outline`, `base_glow`, `glow`, `base_material` and `material`.

![A warm highlight moves through white lettering. Each highlighted syllable grows and settles inside a dark keyline, lavender rim and violet halo.](../examples/assets/soft-front-vocal.gif)

For example, combining a 2 px dark primary outline, a 3 px lavender `SecondaryOutline`, a violet `Glow` halo and a 14 px `hook_feather` keeps lettering readable over both bright and dark video frames. Setting `glow=None` leaves the halo off.

## Choose a highlight mode

Watch the final held note in these three synchronised renders. Only the `highlight` option changes.

![Three synchronized rows show the default wipe with a pulse, a steady wipe, and a color change when the same long note ends.](../examples/assets/highlight-motion.gif)

| `highlight` | Behaviour |
| --- | --- |
| `none` | Steady timed colour wipe with no scale pulse |
| `no_wipe` | Switches the entire timed unit at the end of its interval, including zero-length units |
| `utopia` | Default. Wipe plus a quick rise to 1.15× over the first quarter of the note (up to 100 ms), then linear release |
| `scanline` | Ordinary wipe with a bright leading band |
| `utopia_scanline` | `utopia` pulse plus leading band |
| `zoom_pulse` | Grows to 1.10× across the timed interval, then returns to normal over 0.30 s |
| `zoom_pulse_scanline` | `zoom_pulse` growth plus leading band |

> [!TIP]
> To verify a template, pause halfway through a long note. A wipe shows both colours across the word, while `no_wipe` holds the before-fill until the note ends.

Fine-tune the highlight front with these options on `KaraokeEffects`:

- **Soft wipe front**: Set `hook_feather` (script pixels or a `Glyph.font_size` expression) to blend fill and outline smoothly behind the moving edge. Add `front_color` to tint the edge itself. Supply matching `base_glow` and `glow` (same `border`, `blur` and `opacity`) to blend the halo across the same edge.
- **Scanline styling**: Adjust `scanline_width` (defaults to 16 px at 1080p, scaled to canvas height) and `scanline_softness` (defaults to 8 px at 1080p; `0` gives a hard band). Both accept `Canvas.height` or `Glyph.font_size` expressions. Set `scanline_mode` to `"color"` (default), `"brighten"` (lifts HSV value by `scanline_brightness`, default `0.60`), `"follow_before"`, or `"follow_after"`. In `"color"` mode, set `scanline_color` (supports `PaintInput` in Hook), `scanline_strength` (`0..1`, supports `PaintInput`), or `scanline_material` (such as a `LyricGradient`).
- **Outline flash**: Set `stroke_flash=True` for a 0.24 s shine pulse along the body outline at each body note onset. Reading checkpoints do not retrigger it.
- **Zoom curve**: Set `zoom_pulse_curve_level` from `0` to `5`. Levels `0` and `1` (default) are linear; levels `2`–`5` ease toward the peak and accelerate away.
- **Sweep direction and slant**: Set `reverse_wipe=True` to sweep each timed unit from right to left while keeping authored word order. On horizontal lyrics, italic or oblique fonts automatically slant the front 19° to the right; pass `sweep_angle=0` for a vertical front or another angle in degrees. For whole-line right-to-left placement or reversed line timing, set `right_to_left=True` or `reverse_timing=True` on `Track` (see [Lay out vocal tracks](tracks.md)).
- **Ruby sweeps**: By default (`ruby_scanline="both"`), scanlines track both body text and ruby readings. Set `ruby_scanline="reading"` to keep the band on the kana alone for fully annotated units. Consecutive reading checkpoints split the host body wipe into equal distances; set `ruby_reading_units=True` to give each visible kana an equal share of the body wipe instead (empty readings `#|` hold the wipe in place).

A repeated interval restarts its pulse, shortening any ongoing release if the next interval starts sooner. Multi-character units share one moving front, and glow or secondary outlines add no travel time.

## Entry and exit transitions

Choose an `entry` and `exit` preset on `KaraokeEffects` to control how lines arrive and depart.

| Entry | Exit | Appearance |
| --- | --- | --- |
| `none` | `none` | Plain cut at the display boundaries |
| `fade` | `fade` | Whole-line opacity fade (default) |
| `slide_in` | `slide_out` | Whole-line horizontal slide with opacity |
| `rise` | `rise` | Whole-line upward drift |
| `char_fade` | `char_fade` | Staggered per-character opacity |
| `char_drip` | `char_drip` | Vertical shear around each character's right edge |
| `spin_flip` | `spin_flip` | Scale and shear around each character's centre |
| `utopia` | `utopia` | Overshooting character entry; rotating, flipping, shrinking exit |
| `tilt_pop` | — | Tilted, overshooting character entry (entry only) |
| `tracking_in` | `converge_out` | Spread letters settle in; letters pull toward the line centre |
| `wave_in` | `scatter_out` | Staggered upward wave; seeded radial scatter |
| `stretch_in` | `stretch_out` | Horizontal glyph stretch with five fading outline echoes in `shine` |
| `glow_in` | `glow_out` | Synchronous glow with horizontal echoes and a sharp core layer |
| `assemble_in` | `dissolve_out` | Square particles assemble into each glyph box or scatter away |
| `sparkle` | `sparkle` | 14-star burst sweeping left to right on entry, right to left on exit |
| `ripple` | `ripple` | Thin hollow rings expand and fade |
| `note` | `note` | Musical notes float upward |
| `petal` | `petal` | Petals sway and turn |
| `snow` | `snow` | Six-branched snowflakes with an open centre |
| `snow_solid` | `snow_solid` | Six-branched snowflakes with a filled centre |

Control transition timing and grouping with these parameters:

- `entry_duration` and `exit_duration` set the full transition window in seconds (default `0.3`). Set `0` to disable that transition. Whole-line fades, slides and glow transitions run synchronously; `char_fade`, `char_drip` and `spin_flip` use a 600 ms envelope; `utopia` uses 700 ms on entry and 750 ms per departing glyph on exit (starting after the following character finishes); geometric and particle transitions accept 120–3000 ms.
- `stagger` sets the fraction of the transition window spread between the first and last character (default `7/12`), leaving the remainder for each character's travel.
- `entry_unit` and `exit_unit` default to `"preset"`. Set either to `"character"` to run the chosen transition independently on every body and ruby glyph in reading order.

Ruby readings follow their host characters during transitions: kana share translation, reveal, or departure pivots with their annotated body characters, while stretch halos and glow echoes stay on the main text. Timed spaces occupy character slots for transition particles, but timing decorations skip spaces.

At video time zero, entrances shorten or disable themselves rather than shifting timing clocks. On a dense automatic track, row handoffs can shorten a zoom release or scale down display-anchored transitions so lines fit without overlapping.

## Timing decorations and particles

Set `decoration` on `KaraokeEffects` to emit seeded ornaments as each body glyph highlights. Supported values are `none` (default), `twinkle` (drifting stars), `twinkle_classic` (in-place breathing stars), `note`, `ripple`, `petal`, `snow` and `snow_solid`. Decorations emit from body text only, never from ruby.

By default, each glyph onset emits one burst: three ripple rings, four petals or snowflakes, seven moving stars, or three classic stars or notes. Tune them with these options:

| Option | Default | Effect |
| --- | --- | --- |
| `particle_size` | `0.4` | Size as a fraction of the font's em size |
| `particle_rate` | `None` | Overrides onset bursts with particles per second of the timed interval (ripples keep three-ring timing) |
| `particle_color` | `None` | Inherits highlight ink; accepts one `Color`, a two-colour `(Color, Color)` pair, `"follow_before"`, `"follow_after"`, `"follow_mix"`, or `"illustrated"` |
| `particle_layers` | `"solid"` | With a follow colour mode, `"stroke"` inherits hard outlines, `"decor"` adds soft glow or shadow, and `"all"` adds both |
| `particle_glow_concentration` | `0` | Glow passes on decorated particles: `-1` hides glow; `0`, `1`, `2` select 1, 2 or 3 passes |
| `max_particles` | `512` | Per-line budget covering entry, exit and timing particles; exceeding it raises an error before creation |
| `seed` | `0` | Deterministic variation, independent of render or seek order |

With `"illustrated"`, highlight particles are white, transition petals are cherry pink, and transition snow is icy blue. When a gradient is active in a follow mode, particles sample the gradient colour (rotating vertical gradients with petals, snow, notes and stars, and sampling horizontal gradients by position across the line).

## Combinations and output

Combine any `entry`, `exit`, `highlight`, `decoration` and `stroke_flash` in one `KaraokeEffects` call. Try combinations quickly using the catalog example script:

```sh
uv run python -m examples.karaoke_catalog build/petals.hook --entry wave_in --exit petal --highlight zoom_pulse --decoration petal
```

![Four built-in combinations](../examples/assets/karaoke-builtins.gif)

`KaraokeEffects` owns the highlight masks on its track, so do not stack a second highlight factory on the same glyphs. You can freely add extra `LyricRule` motions or custom `line.schedule(...)` rules alongside it.

> [!NOTE]
> The catalog implements the visual families familiar from karaoke animation menus (entries, exits, highlights, decorations and outline flash) as an independent engine. It is not an importer or pixel-identical clone of any external editor.

Browser preview and playback shader export support the full catalog, including feathered wipes, slanted fronts, gradients, soft scanlines, and particle transitions. Return a `LyricScene` from your template, then call `scene.preview()` to check the effects.

Standard ASS export (`scene.ass.compile().document.save("song.ass")`) supports hard-edged wipes (`hook_feather=0`), native fades and eligible transforms; gradients, feathered wipes, soft scanlines and complex particle trajectories raise `SceneCompileError`. See [Preview and export](../output/README.md) and [Export standard ASS](../output/ass.md) for format trade-offs.

## Compose editable effects

`effect_components()` describes each component's slot, supported targets, and controls. Pass `script_height=...` to get defaults and bounds for the script resolution. The default height is 1080 pixels. Apply selections to a `Track` with `compose_track()`. It raises an error if selections share a single-selection slot and overlap on the same target. Echoes and particles can appear more than once.

```python
from kara_templater import ComponentSelection, Track, compose_track

track = compose_track(
    Track(id="lead"),
    (
        ComponentSelection("entrance", "entry-fade"),
        ComponentSelection(
            "band", "highlight-scanline",
            values={"scanline_width": 18},
            bindings={"scanline_width": "lead_scan_width"},
        ),
    ),
    script_height=720,
)
```

The bound `scanline_width` updates live. Changing entry duration requires rebuilding the scene with the new timing. For typography, supply the track's `Style` records and set `target` to `"body"` or `"ruby"`. Use one track per vocal stream and apply its own selections. [Component coverage index](../examples/component-coverage.md) · [Live material inputs](materials.md#live-parameters-with-paintinput)

## Next steps

- Style wipes with gradients, glows and WGSL shaders in [Colour and materials](materials.md).
- Write custom motion rules and curves in [Animation and timing](animation.md).
- Build custom particle emitters and onset echoes in [Particles, copies and echoes](particles.md).
- Find preview and delivery options in [Preview and export](../output/README.md).
