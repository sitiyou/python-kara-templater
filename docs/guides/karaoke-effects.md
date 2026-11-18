# Built-in karaoke effects

`KaraokeEffects` puts entry, singing, exit, particles and outline flash in one
`Track.effects` entry. Each option expands into the same Scene objects and lyric
rules available to custom effects. You do not schedule each character manually.

## Read the singing position from the lettering

Use `Track(id="main", effects=(KaraokeEffects.duotone(),))` for a timed wipe
that changes the fill and outline together. Unsung letters have dark ink with a
pale rim. As the front crosses a letter, the sung side takes on a warm pale fill
and a copper outline. The holes remain transparent. Four keyword colors
(`unsung`, `unsung_outline`, `sung`, `sung_outline`) control the two looks.
The default transition is 24 script pixels wide and centered on the singing
position. Set `feather` to roughly a third of the displayed glyph width and
preview a held note. The GPU hook interpolates both color pairs continuously.
For simple timed lyrics, compact ASS approximates the same profile with up to
8 moving color strips plus the two endpoint colors per cluster. Set
`feather=0` for a sharp boundary and smaller ASS.

## Recommended main vocal

![A warm singing front moves through white lettering. Each sung syllable grows and settles inside a dark keyline, lavender rim and violet halo.](../examples/assets/soft-front-vocal.gif)

A narrow dark outline keeps the letter legible on a bright frame. A wider
lavender rim separates it from a dark frame. Behind both, a violet halo softens
the silhouette. Inside the letter, a 14 px transition mixes white into apricot
as the word is sung. The note reaches 112% scale just over a third of the way
through its own duration and settles back by the end. In the preview, compare
the short first note with the held final note.

```python
from kara_templater import (
    Color, Document, FadeIn, FadeOut, Glow, Layout, Line, LyricHighlights,
    LyricRule, LyricSweep, ScalePulse, StatePatch, Style, Track, Vec2, prepare_tracks,
)

document = Document.create(width=640, height=360, styles=(
    Style(fontname="Sarasa UI J", fontsize=60, bold=True, outline=2, shadow=0),
))
document.records.extend((
    Line(start_time=1000, end_time=3000, text=r"{\k30}風{\k50}の{\k120}色"),
    Line(start_time=3100, end_time=4600, text=r"{\k45}空{\k35}の{\k70}音"),
))

motion = (
    LyricRule("line", "enter", FadeIn(), duration=0.18),
    LyricRule("syllable", "singing", ScalePulse(peak=1.12, peak_at=0.36)),
    LyricRule("line", "exit", FadeOut(), duration=0.22),
)
rim = StatePatch(outline=Color.hex("#D4B6FF"), border=5)
halo = Glow(Color.hex("#8054CD"), border=8, blur=4, opacity=0.75)
back = LyricHighlights.from_singing(rim, base_paint=rim, glow=halo, base_glow=halo)
face = LyricSweep(fill=Color.hex("#FF984A"), width=14, step=1)
layout = Layout(rows=2, position=Vec2(42, 110), gap=100)

scene = prepare_tracks(document, tracks=(
    Track(id="rim", layout=layout, effects=(back, *motion)),
    Track(id="face", layout=layout, reserved_border=5, effects=(face, *motion)),
))
scene.compile(native_tweens=True).document.save("karaoke.ass")
```

The two tracks draw the same timed lyrics at the same positions, back layer
first. Both views reserve the outer 5 px hard rim so their glyphs stay aligned. The face retains the source style's 2 px outline. Tune `width` to change
how much of the letter contains intermediate colors; tune `halo.blur` to change
how far the light spreads outside it. The sizes above accompany a 60 px font.
For an existing song, load its Document and select the same main-vocal sources
for both views. Render a verse before compiling a whole song: the soft front
uses color bands in standard ASS, and the pulse moves those bands with the text.

## Choose the singing motion

`Track.effects` defaults to an empty tuple. Add `KaraokeEffects()` to get the
catalog defaults: a 0.30 s fade at each end of the line and a white-to-coral
wipe during singing. Watch the final held syllable in these synchronized
renders; only the singing setting changes.

![Three synchronized rows show the default wipe with a pulse, a steady wipe, and an immediate color change on the same long note.](../examples/assets/singing-motion.gif)

| What you want the singer to see | What to write |
| --- | --- |
| The color travels across the word and the glyph briefly grows | `KaraokeEffects()` (default singing mode `utopia`) |
| The color travels across the word while the glyph stays still | `KaraokeEffects(singing="none")` |
| The entire timed unit changes color when singing finishes | `KaraokeEffects(singing="no_wipe")` |

To check a template, pause halfway through a long note. The wipe leaves
both colors visible; the onset switch has already painted the whole unit.
The full scene and hook carry the pulse. Compact ASS keeps the color timing
and line fades and simplifies glyph motion. When outline clearance moves glyphs,
compact ASS positions clusters separately to retain the corrected spacing. For count-in direction see
[Choose the countdown order](text-and-cues.md#choose-the-countdown-order).

The catalog covers the animation menus in
[Karaoke Studio / Lin-K Lyrics](https://github.com/karaoke-studio/karaoke-studio):
19 entry choices, 19 exit choices, 7 singing choices and 8 singing-decoration
choices, including `none`, plus outline flash. This is an independent implementation
of those visual families, not an importer or a pixel-identical replacement for
its Qt/Direct2D renderer.

## Lyric-building elements

| Studio element | Available in this library | Coverage |
| --- | --- | --- |
| Timed lyrics, independent voices, ruby and repeat readings | `Document`, `Track`, `LyricLine` | Source syllable clocks and measured body/ruby. Separate main and harmony tracks can use different styles. |
| Horizontal lyric lanes | `KaraokeRows`, `Layout.allocate` | One to eight Studio-style rotations, top/center/bottom blocks, independent row alignment and offsets. Custom allocators handle exceptional lines and lead resets. |
| Singing paint, stroke, shadow, glow, ramps and particles | `KaraokeEffects`, `LyricHighlights`, materials | The catalog implements the animation families. Appearance depends on font metrics, rendering backend and selected material. |
| Inline volume signal | `VolumeCue` | Whole-group flashes, then successive sung-color fills. In this library the cue ends at its own boundary, even when the host lyric stays visible. |
| Floating shape lamps, count-in text and vector guide marks | `SignalCue`, `TextCue`, `CuePreset` | Seven built-in lamp shapes and custom paths. Cues can be inline or independently positioned. Shape lamps inherit the sung palette. Their colors and size can be overridden. |
| Studio page timing and alternate writing modes | Partial | Horizontal presets handle lane reuse, section gaps, synchronized page entry/exit, tail extension and smart margins. Imported page breaks, native vertical writing and mirrored right-to-left lyric layout have no equivalent preset. |
| Role-linked signal styling and timed character replacement | Partial | Built-in signals inherit solid lyric colors or take an explicit role palette. Signals scale static hard outer strokes and glow to their own dimensions. Leading inline volume bars share a sung horizontal gradient with their lyric line. Independent lamps keep a fixed gradient over all countdown slots. Timed guide-glyph replacement needs a custom drawing. |

See [Tracks](tracks.md), [text and cues](text-and-cues.md) and the
[signal preview](../examples/README.md#karaoke-count-ins).

## Entry and exit

| Entry | Exit | Appearance |
| --- | --- | --- |
| `none` | `none` | Keep the ordinary display lifetime |
| `fade` | `fade` | Whole-line opacity |
| `slide_in` | `slide_out` | Whole-line horizontal movement and opacity |
| `rise` | `rise` | Whole-line upward movement |
| `char_fade` | `char_fade` | Staggered character opacity |
| `char_drip` | `char_drip` | Corner-pivot shear, like a hanging letter |
| `spin_flip` | `spin_flip` | Centered scale and shear |
| `utopia` | `utopia` | Overshooting entrance; rotating, flipping, shrinking exit |
| `tracking_in` | `converge_out` | Spread letters settle; letters converge toward the measured line center |
| `wave_in` | `scatter_out` | Staggered upward arrival; seeded radial scatter |
| `stretch_in` | `stretch_out` | Each glyph stretches horizontally with five fading white outline layers. The core outline and halo widen along with the glyph. |
| `glow_in` | `glow_out` | Synchronous glow with horizontal echoes and a sharp text layer |
| `assemble_in` | `dissolve_out` | Square particles converge on points within each glyph box or scatter outward |
| `sparkle` | `sparkle` | A 14-star burst sweeps across the line, left to right on entry and right to left on exit |
| `ripple` | `ripple` | Thin hollow rings expand and fade |
| `note` | `note` | Musical notes float upward |
| `petal` | `petal` | Petals sway and turn while entering/leaving |
| `snow` | `snow` | Six-branched snowflakes with an open center |
| `snow_solid` | `snow_solid` | Six-branched snowflakes with a filled center |

`entry_duration` and `exit_duration` are seconds for the complete transition.
`stagger` is the fraction of that duration assigned to delay between the first
and last character (default 7/12); the remainder is each character's travel.
Studio’s character fade, drip and flip use a 600 ms window. Utopia uses 700 ms for entry (200 ms stagger and 500 ms motion) and 750 ms per departing glyph. Geometric/particle transitions accept 120–3000 ms. Whole-line fades/slides and glow transitions are synchronous. Zero duration
turns off that transition.

The entry fades to full opacity early enough that its movement stays visible.
Exit reserves time after the last singing interval, including a zoom release.
At Scene zero, an entry is shortened or disabled rather than shifting singing
clocks. Explicit effect occupancy can require an additional row or cause a layout
capacity error; reduce the effect duration or adjust the allocator in that case.

Differences from the reference include seeded trajectories, independently drawn
ornament shapes, seeded particle placement and eased motion. Utopia exit begins after the following character finishes; the final character
uses the remaining display tail. Its departure lasts 750 ms. Snow's open-center version is an original
six-branch drawing, not a copy of the reference sprite. Assembly is an illusion
built from moving squares and a separate glyph opacity curve.

## Singing and decoration

| `singing` | Behavior |
| --- | --- |
| `none` | Ordinary timed color wipe; the name follows the source menu |
| `no_wipe` | Recolor the entire timed unit at completion, including zero-duration units |
| `utopia` | Eased 1.15× pulse peaking at 25% of the note or 100 ms, whichever comes first |
| `scanline` | Ordinary wipe with a narrow luminous leading edge |
| `utopia_scanline` | Pulse plus leading edge |
| `zoom_pulse` | Grow to 1.25× throughout singing, then return to normal over 0.30 seconds |
| `zoom_pulse_scanline` | Sustained growth plus leading edge |

A repeated interval restarts the pulse; its release is shortened if the next
interval begins sooner. Multi-character units share one moving front. Ruby uses
its own measured reading width but the same source interval. Outline and glow
padding never increase the singing distance.

`decoration` accepts `none`, `twinkle`, `twinkle_classic`, `note`, `ripple`, `petal`,
`snow` and `snow_solid`. Modern twinkle drifts; classic twinkle stays in place and
breathes in size/opacity. Ornaments attach to the original glyph's parent and
move independently after birth. They are emitted from body text, not ruby.

- `particle_size`: fraction of the shaped font’s em size, default 0.40.
- Snow enters across the full line and is already falling when the line appears. Petals arrive glyph by glyph. The line’s exit clips the remaining transition particles.
- Singing emits one burst per glyph onset. The defaults are three ripple rings, four petals or snowflakes, seven moving stars, or three classic stars or notes. Set `particle_rate` to choose a density per second of singing. Ripple keeps its three-ring timing.
- `particle_color` overrides the built-in palette. Singing particles default to white. Entry and exit particles alternate two cherry pinks, or two icy whites for snow.
- `max_particles`: total entry/exit/singing particle budget per line, default 512;
  exceeding it raises before particle factories execute.
- `seed`: deterministic variation, independent of rendering or seeking order.
- `zoom_pulse_curve_level` controls the zoom attack and release. Levels 0 and 1 are linear (Studio default 1). Levels 2–5 ease toward the peak and accelerate away from it.
- `scanline_mode="brighten"` lifts the brightness of each side’s fill and outline independently, including the stops of each side’s linear gradient. `follow_before` and `follow_after` use one side’s palette across the whole band. `scanline_brightness` sets the fraction of remaining HSV value to add (default 0.60).
- `scanline_mode="role"` takes a reusable paint or a per-target factory in `scanline_material`. For example, pass a singer’s `LyricGradient` to color both the glyph and its outline inside the band. A missing paint falls back to `scanline_color`. With horizontal role gradients,
  the resting text uses each singer’s full ink span. The static scanline samples
  the current contiguous run; a zoom-pulse scanline uses the moving glyph’s advance.
- In the default `color` mode, `scanline_color` sets the band color for both fill and outline (default white). `scanline_softness` sets the inward falloff on each side, default 8 px at 1080p. Zero gives a hard band.
- `scanline_width`: script pixels, omit for a band of 16 px at 1080p, scaled to script height. An explicit width uses script pixels. At a syllable handoff the band can light ink on both neighboring glyphs. During a timing gap the band disappears.
- For a soft color change in the standalone GPU hook, use
  `KaraokeEffects(singing="utopia", hook_feather=17, sung_outline=Color.hex("#522432"))`.
  The final 17 script pixels behind a single-interval sweep edge mix the unsung
  and sung inks inside the glyph and outline masks. Both the waiting and sung gradients retain their colors through the feather. To carry the same transition into a halo, supply both glow
  colors with matching border, blur and opacity. Ordinary ASS and repeated
  intervals retain the basic wipe. Choose a scanline mode when you want an
  additional bright stripe. With a feathered hook, set `front_color` to give
  the moving edge a distinct color inside the fill and hard outline. The halo
  retains its softer color transition.
- `stroke_flash=True`: a 0.24-second white contour pulse at each body-glyph onset.

`sung` and `unsung` set the basic fill colors. `material`, `glow` and `base_glow`
accept the same fields/factories as `LyricHighlights.from_singing`, including
`LyricGradient`. The recipe owns highlight masks: do not stack another highlight
factory on the same glyphs. Additional custom effects can use `line.schedule(...)`
or ordinary `LyricRule`; overlapping writes retain the normal conflict diagnostics.

## Recommended combinations and previews

![Four built-in combinations](../examples/assets/karaoke-builtins.gif)

Each panel uses identical lyrics, timing, font and layout. These are actual
libass renders, not mockups. Read [recommended designs](../tutorials/karaoke-design.md#built-in-animation-combinations)
for when to use each combination.

```sh
uv run python -m examples.karaoke_catalog build/petals.ass --entry wave_in --exit petal --singing zoom_pulse --decoration petal
uv run python -m tools.render_karaoke_catalog build/karaoke-catalog
```

[Example source](../../examples/karaoke_catalog.py) and
[catalog renderer](../../tools/render_karaoke_catalog.py). The renderer writes a
640×360/60fps video and ASS for each choice,
plus four combinations, with event counts and hashes in its manifest.
Use `--only design-` to regenerate just the recommendations.

## Output and costs

All catalog options can compile to standard ASS. Rotations, dynamic blur and
particles can generate many events; the catalog is not a promise of small ASS
files. Inspect `Scene.compile()` reports and keep ordinary player limits in mind.

The same Scene can use [GPU-enhanced output](gpu-rendering.md). Continuous gradients
then avoid ASS color bands. Changing native blur still requires different coverage
masks in the current GPU adapter; it is not a general GPU blur shader. The tests
exercise draw preparation for every catalog choice. Local validation includes
actual libass videos and a GPU-enhanced example; Windows Direct2D parity is not claimed.

For custom timing curves, independent ornament clocks or different particle
geometry, use [animation](animation.md) and [particles](particles.md). Built-ins
are a short authoring path into those same mechanisms.

## Export a song

Keep the visual recipe in a module that accepts a prepared Document and returns
the LyricScene from `prepare_tracks`. A separate entry point can load the lyrics
and write both playback files from that same scene.

```python
from kara_templater import Document

from l4ts_template import build

scene = build(Document.load("L4TS.document.ass"))
scene.export_compact_ass("L4TS.ass")
scene.export_hook("L4TS.hook", fps=60)
```

The compact ASS approximates catalog motion, materials and particles with native
karaoke timing, the recipe's sung/unsung colors and line fades. It keeps inline
cue space and drawings. Duotone lyrics retain ruby positions and reading clocks
in compact output. Other ruby recipes, complex timing and internal inline cue
reservations use ordinary scene compilation, so their output can be larger. The hook carries the
full effects. Choose one of the two outputs for playback.
