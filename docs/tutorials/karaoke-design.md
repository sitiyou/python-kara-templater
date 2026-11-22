# Design a karaoke layout

For a finished main vocal, start with the [layered soft-front recipe](../guides/karaoke-effects.md#recommended-main-vocal).
Its two visual layers share a layout and the original singing clock. Inspect a short and a held syllable against
both light and dark frames.

At 1920 × 1080 the default two-row `KaraokeRows` layout leaves 50 px at the sides and 60 px at the bottom of the Track region. With a full-frame region, the bottom inset is 40 px at 720p. Short lines move inward together according to their widths,
including any inline cue. The preset fits the body, outlines and readings of co-visible rows, then adds 45 px between them. Its margins and clearance scale with canvas height.
For a custom origin or alignment, `Layout(rows=2)` places rows downward from the chosen origin, with measured row heights plus 20% of the largest body font size between rows. The bottom clearance then depends on the origin and the visible lyrics.

For horizontal main vocals at 1080p, start with 100 script pixels for the body
and 45 for ruby in the source styles. Scale both with canvas height. Preview
the longest line and the densest readings at delivery size, then adjust either
size to suit the typeface and the visual style.
For main, harmony and ruby typeface choices, see [Choose a typeface for sung lyrics](../guides/fonts-and-preview.md#choose-a-typeface-for-sung-lyrics).
Set a separate region and an explicit layout for an upper harmony Track. Align
a countdown with the phrase it introduces and check both when visible together.

Adding `KaraokeEffects()` fades the line in and out over 0.30 s each and changes white
to coral as the syllable pulses. Track requests 5 s of preview. Its automatic tail targets 1.0 s including the exit animation. Dense handoffs shorten the hold and, when necessary, the transitions. Custom allocators and explicit Track
values take precedence. The CLI source-style recipe preserves ASS alignment and
margins. [Studio style and layout definitions](https://github.com/karaoke-studio/karaoke-studio/blob/54f06eb7d75624b88bd36ba347e932ccc17a199b/krok_helper/subtitle_render/domain/models.py)

## Built-in animation combinations

For new karaoke templates, start with the [built-in catalog](../guides/karaoke-effects.md).
Use these optional combinations for phrases that call for more motion.

| Design | Entry / singing / exit | Decoration | Use |
| --- | --- | --- | --- |
| Clear | `tracking_in` / `scanline` / `char_fade` | Outline flash | A readable whole-song treatment with visible but restrained motion |
| Sakura | `wave_in` / `zoom_pulse` / `petal` | `petal`, 5 births/s, size 0.18 | Gentle passages; a pink singing fill and slow petal flutter |
| Luminous | `glow_in` / `utopia_scanline` / `stretch_out` | `twinkle` | Short emphatic phrases; let the blurred light streak settle before singing |
| Crystal | `assemble_in` / `scanline` / `dissolve_out` | `snow`, 4 births/s | Selected transitions where gathering and dispersing particles reinforce the phrase |

These combinations are configurations of `KaraokeEffects`, not separate engines.
For example, use this as one Track effect:

```python
from kara_templater import Color, KaraokeEffects

sakura = KaraokeEffects(
    entry="wave_in", singing="zoom_pulse", exit="petal", decoration="petal",
    sung=Color(255, 160, 205), particle_size=0.18, particle_rate=5, seed=17,
)
```

Keep main lyrics and harmony on separate Tracks. Give harmony fewer particles
and a smaller pulse; do not apply the main line's elaborate exit to every layer
by default. Test long notes, clipped preview windows and row handoffs before
using a combination throughout a song. Particle density is per timed glyph, so
an English word containing several independently drawable letters can emit more
particles than one Japanese character with the same duration.

The [catalog renderer](../../tools/render_karaoke_catalog.py) contains the exact
four configurations and produces each as a standalone video. Its previews use
original text, not downloaded reference footage. Reference motion was inspected
using the local Studio QPainter fallback; different font/rasterizer output and
our documented timing differences mean these are visual-family adaptations.

