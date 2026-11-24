# Design a karaoke layout

For a finished main vocal, start with the [layered soft-front recipe](../guides/karaoke-effects.md#recommended-main-vocal).
Its two visual layers share a layout and the original timing clock. Inspect a short and a held syllable against
both light and dark frames.

At 1920 × 1080 the default two-row `KaraokeRows` layout leaves 50 px at the sides and 60 px at the bottom of the Track region. With a full-frame region, the bottom inset is 40 px at 720p. Short lines move inward together according to their widths,
including any inline cue. The preset fits the body, outlines and readings of co-visible rows, then adds 45 px between them. Its margins and clearance scale with canvas height.
For a custom origin or alignment, `Layout(rows=2)` places rows downward from the chosen origin, with measured row heights plus 20% of the largest body font size between rows. The bottom clearance then depends on the origin and the visible lyrics.

For horizontal main vocals at 1080p, start with 100 script pixels for the body
and 45 for ruby in the source styles. Scale both with canvas height. Preview
the longest line and the densest readings at delivery size, then adjust either
size to suit the typeface and the visual style.
For main, harmony and ruby typeface choices, see [Choose a typeface for lyrics](../guides/fonts-and-preview.md#choose-a-typeface-for-lyrics).
Set a separate region and an explicit layout for an upper harmony Track. Align
a countdown with the phrase it introduces and check both when visible together.

Adding `KaraokeEffects()` fades the line in and out over 0.30 s each and changes white
to coral as the syllable pulses. Track requests 5 s of preview. Its automatic tail targets 1.0 s including the exit animation. Dense handoffs shorten the hold and, when necessary, the transitions. Custom allocators and explicit Track
values take precedence. The CLI source-style recipe preserves ASS alignment and
margins. [Studio style and layout definitions](https://github.com/karaoke-studio/karaoke-studio/blob/54f06eb7d75624b88bd36ba347e932ccc17a199b/krok_helper/subtitle_render/domain/models.py)

## Built-in animation combinations

For new karaoke templates, start with the [built-in catalog](../guides/karaoke-effects.md).
Use these optional combinations for phrases that call for more motion.

| Design | Entry / timing / exit | Decoration | Use |
| --- | --- | --- | --- |
| Clear | `tracking_in` / `scanline` / `char_fade` | Outline flash | A readable whole-song treatment with visible but restrained motion |
| Sakura | `wave_in` / `zoom_pulse` / `petal` | `petal`, 5 births/s, size 0.18 | Gentle passages; a pink timing fill and slow petal flutter |
| Luminous | `glow_in` / `utopia_scanline` / `stretch_out` | `twinkle` | Short emphatic phrases; let the blurred light streak settle before timing |
| Crystal | `assemble_in` / `scanline` / `dissolve_out` | `snow`, 4 births/s | Selected transitions where gathering and dispersing particles reinforce the phrase |

These combinations are configurations of `KaraokeEffects`, not separate engines.
For example, use this as one Track effect:

```python
from kara_templater import Color, KaraokeEffects

sakura = KaraokeEffects(
    entry="wave_in", highlight="zoom_pulse", exit="petal", decoration="petal",
    after_fill=Color(255, 160, 205), particle_size=0.18, particle_rate=5, seed=17,
)
```

Keep main lyrics and harmony on separate Tracks. Give harmony fewer particles
and a smaller pulse; do not apply the main line's elaborate exit to every layer
by default. Test long notes, clipped preview windows and row handoffs before
using a combination throughout a song. Particle density is per timed glyph, so
an English word containing several independently drawable letters can emit more
particles than one Japanese character with the same duration.

Try these combinations in the [karaoke catalog example](../../examples/karaoke_catalog.py).

## Mark timing without a color wipe

Use `LyricHighlights.from_timing(..., wipe=False)` to switch the entire timed
unit to its highlight color at release. For a cue at the attack, bind a short
`ScalePulse` to each syllable's timing interval. The example uses both cues so
the lyric still shows where to sing during a sustained note.

For an ornament that follows the current syllable, read its measured center
through the scene evaluator at the note onset. Keep the ornament above the row
and let it settle on the next center at the next onset. Scale the travel time
to the gap between onsets so the motion remains readable in fast phrases.
Check the beginning, a sustained note, and a line handoff in playback.
[Runnable example and preview](../examples/README.md#karaoke-without-a-color-wipe)

## Reveal a phrase from narrow openings

A short horizontal slide behind a fixed cut makes the letters look as if they
emerge from beneath the surface. The four characters in ProFilE enter from
right to left. The cut and its one-sided shadow
stay put while each glyph moves left. The first visible displacement is already
smaller than the glyph's width and the following increments shrink quickly.
At 30 fps the movement settles over about eight frames, with a one-frame
stagger between adjacent characters. [ProFilE around 1:47.7](https://www.bilibili.com/video/BV1s14y1w72b/?t=107.7)

For a lyric pre-entry, put the cut just beyond each character's final ink
bounds, including marks and outlines. Start from a displacement that hides the
complete glyph. A measured starting point for the remaining displacement at
equal time steps is `1.00, 0.58, 0.35, 0.21, 0.12, 0.07, 0.03, 0.01, 0.00`.
Use the short stagger on a compact phrase so the last character settles before
its timing highlight. For longer lines, group characters by word or syllable
and measure each opening around the combined ink bounds of the body and ruby.
A tested two-row example with 13 and 11 syllable groups uses that shared opening
and finishes the motion about 0.40 s before each pickup. Check the
outgoing row while the next row is entering, especially if the singers overlap.

The default style of the fixed-cut example places the glyphs directly over the
footage. An invisible clip reveals the moving ink through each fixed opening.
On the dark preview background,
off-white letters turn pale amber as the wipe advances. For footage with
changing brightness, a thin outline around the glyphs can preserve contrast.
Inspect at delivery size and keep the whole body and its readings visible
during timing. [Fixed-cut example](../examples/README.md#fixed-cut-lyric-reveal)

## Bring fixed lyrics in and out of focus

The lettering in *500 Nanometres of Fiction* has visible cells in the middle
of the frame and broader edges near the top and bottom. Measurements in the
middle gave a similar edge spread at different speeds. Use the pixel grid and
defocus radius as separate controls. [Source around 2:11.3](https://www.bilibili.com/video/BV1ArBXBSEc3/?t=131.333)

Keep the baseline fixed. A tested entrance reduces a Gaussian radius from
about 4.2 px to zero over 360 ms on a 1080p canvas. Fade in as the shape first
becomes readable and hold the sharp lyric for about 320 ms before the pickup.
After the last note and a short readable hold, increase the radius and fade
over the exit. Keep the body and ruby sharp for the whole timing interval.

For a digital texture, average the glyph coverage over fixed screen cells.
The comparison uses 7 px cells for a 92 px body. Ease the blend between the
cell averages and the original coverage. For softer cells, reduce their edge
blur first and finish by fading the cell contribution to zero. A fixed cell
size keeps the grid stable over the transition.

A single ASS text object can tween `StatePatch(blur=0)` from an initial
`VisualState(blur=5)` to enter in focus. A blur-channel tween does not export as
native Hook motion. For Hook, use `ShaderPaint` with prefiltered coverage masks
at several radii and interpolate adjacent masks. Return to the ordinary timed
lyric for timing. Match the animation to the note timing and inspect small
readings at delivery resolution.

## Type the lyric in and erase it after timing

Dreamin'Her uses a cursor that travels with the end of the visible text.
Adapt that timing to the lyric itself. Reveal shaped units from left to right
before the pickup, keeping each reading with its body glyphs. Move the caret
to the last visible glyph, then clear it once the complete line is ready to
read. [Dreamin'Her around 0:31](https://www.bilibili.com/video/BV1hM4m1C7GN/?t=30.92)

After the last note, hold the complete phrase briefly and shorten the visible
suffix from right to left. Use the same measured caret positions in reverse.
The tested short phrase uses roughly 75 ms per unit, with the complete line
ready about 0.35 s before timing. Keep the glyphs on their final baseline
throughout and preserve the original timing clocks when adjusting their
visibility. Draw the caret beside the text over the footage.

## Bring syllables in from different edges

In the source title, four characters cross the left, upper, lower and right
edges of one viewport. They travel different distances and share one easing
curve, so they finish together. A thin pale typeface against the dark teal
scene makes the separate paths easy to see. [Source title around 0:23.7](https://www.bilibili.com/video/BV17z4y1R7iD/?t=23.666)

Use `ProgressCurve.cubic_bezier(.17, .17, 0, 1).at` with a position tween to
get the source's quick travel and long deceleration. For a highlight line, shorten
the move to fit the preview window. Measure each syllable's viewport from its
body and ruby ink, including the outline, then move the syllable and its
reading as a group. This keeps the reading above the same glyph during the
entry. Check that the entire line is visible before the pickup and during an
overlap with the next row. A pale body color and a brighter blue timing color
can keep the change readable on a dark background.

## Give each timing state its own outline

The NicoKara edition of L’Amour et le Crâne pairs white waiting text with
a cyan outline, then changes the same region to deep blue with a white
outline. The small dark shadow remains visible beneath both appearances.
The two-state outline helps keep the lyric legible where the background
cuts between dark artwork and near-white frames. [NicoKara around 0:40](https://www.bilibili.com/video/BV1pLjpzbEm1/?p=2&t=40)

Set the fill, outline, and shadow in the two paint states of
`LyricHighlights.from_timing`. The source gives a starting palette of
`#FFFFFF` with `#349DEA` for waiting and `#000EFF` with `#FFFFFF` for highlight.
On the study's 1080p canvas, a 2.4 px body outline and a shadow offset
around `Vec2(1.5, 2)` give a similar treatment. Scale the width with the
type size and inspect the reading separately. A smaller outline keeps
the ruby counters open.

Let the standard timed wipe sweep the body and the reading over their own
widths. The reference holds its front between notes and moves slowly on
the final syllable. Preview the hold and at least one bright and one dark
shot. A short fade makes the shadow visible through the translucent face,
so inspect a partially faded frame as well as the resting style.

## Break only the last glyph after the release

The Ticket title in Dream and Its Symbol compresses toward the center of the
frame and rebounds as the last two letters separate into offset bands. The
early letters move together while small fragments travel farther at the
right edge. [Ticket around 2:35.433](https://www.bilibili.com/video/BV1kV4y1o7fP/?t=155.433)

Keep the timed lyric and its readings intact through the last note. After a
short hold, use `text_to_path` to get the final glyph at its original position
and `split_path(..., cells=...)` to cut its outline with angled bands. Send
the bands in different directions with `DriftOut`. Fade the reading as the
glyph releases. On an alternating layout, let the incoming row keep its usual
position and timing. Inspect the overlap between the moving pieces and the
next row on the actual background.
