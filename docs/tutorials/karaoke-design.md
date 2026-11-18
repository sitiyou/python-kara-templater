# Design a karaoke layout

For a finished main vocal, start with the [layered soft-front recipe](../guides/karaoke-effects.md#recommended-main-vocal).
Its two visual layers share a layout and the original singing clock. Set the
row geometry for the song, then inspect a short and a held syllable against
both light and dark frames.

At 1920 × 1080 the default two-row layout has 50 px side margins and a 60 px
bottom inset. Short lines move inward together according to their widths,
including any inline cue. The grid uses the track's body ascent, descent and
hard outlines, with 45 px between body boxes. A top-anchored track reserves
reading space above the first baseline across pages. Margins and row spacing scale with script
height. The source styles supply the actual fonts and sizes. Studio's own
typographic reference at this resolution is 100 px body and 45 px ruby.
For main, harmony and ruby typeface choices, see [Choose a typeface for sung lyrics](../guides/fonts-and-preview.md#choose-a-typeface-for-sung-lyrics).
Set a separate region and an explicit layout for an upper harmony Track. Align
a countdown with the phrase it introduces and check both when visible together.

The default effect fades the line in and out over 0.30 s each and changes white
to coral as the syllable pulses. Preview and tail request 1.8 s and 1.0 s.
Row handoffs can shorten this padding. Custom allocators and explicit Track
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

