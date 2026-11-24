# Effect gallery

Pick an effect by its preview, then run its example from a source checkout.
Use the fonts in the example to match the lyric layout, and choose an export
format that supports the effect. [Get started](../getting-started.md) · [Output formats](../guides/choosing-output.md)

## Find an example by its visual goal

Choose the row that best matches what you want to change. For a list of every built-in
entry, timing, exit and ornament, start with [the effect catalog](../guides/karaoke-effects.md).

| Visual goal | What the example shows | Where to start |
| --- | --- | --- |
| Set a typeface and keep lyrics clear as footage changes | A dark keyline, a colored rim and a soft halo around the same lettering | [Layered main vocal](../guides/karaoke-effects.md#recommended-main-vocal) · [Typeface and reading choices](../guides/fonts-and-preview.md#choose-a-typeface-for-lyrics) |
| Compare whole-song motion | Combine different entrances, note highlights and exits around the same lyrics | [Built-in combinations](#start-with-a-whole-song) · [Eight motion studies side by side](../tutorials/lyric-studies.md#what-differs) |
| Place alternating rows or overlapping voices | Independent lead and harmony Tracks with layout, palettes and a common recording clock | [Row allocation example](../../examples/lyric_orchestration.py) · [Track palettes and cues](../../examples/karaoke_designs.py) |
| Indicate a note attack or release | A moving marker cues the attack, a short pulse accents it, and the whole glyph changes color at release | [Karaoke without a color wipe](#karaoke-without-a-color-wipe) |
| Give the entrance a distinctive silhouette | Characters slide through invisible cuts, keeping the reading with its character | [Fixed-cut lyric reveal](#fixed-cut-lyric-reveal) |
| Bring text into focus, type it in, or break it apart | Separate entry and exit mechanisms with guidance on preserving readability while the line is active | [Focus and pixelation](../tutorials/karaoke-design.md#bring-fixed-lyrics-in-and-out-of-focus) · [Typing and erasing](../tutorials/karaoke-design.md#type-the-lyric-in-and-erase-it-after-timing) · [End-glyph breakup](../tutorials/karaoke-design.md#break-only-the-last-glyph-after-the-release) |
| Design a count-in that matches the song | Flashing columns, independently clearing shapes and a vector motif that pulses on each beat | [Karaoke count-ins](#karaoke-count-ins) · [Custom paw cue](#paw-countdown-and-character-flips) |
| Add color or motion alongside the text | Gradient paint, glyph copies, and ornaments with their own lifetimes | [GPU gradient](#gpu-gradient) · [Copies and reveals](../tutorials/lyric-studies.md#copies-exits-and-reveal) · [Independent ornament and text clocks](../tutorials/lyric-studies.md#independent-ornament-and-text-clocks) |

## Start with a whole song

**Built-in karaoke effects.** Mix an entrance, a timing treatment, and an exit
with `KaraokeEffects`. The preview shows four combinations using Sarasa UI J.

![Four combinations of lyric entrances, timing highlights, and exits](assets/karaoke-builtins.gif)

```sh
python -m examples.karaoke_catalog build/studio.hook --entry glow_in --exit dissolve_out
```

[Catalog source](../../examples/karaoke_catalog.py) · [Choose effects](../guides/karaoke-effects.md)

**Lead and harmony.** See how independent Tracks share a song clock, rotate
rows, and use different colors. [Row allocation](../../examples/lyric_orchestration.py) · [Track palettes](../../examples/karaoke_designs.py)

## Animate the lyric

### Fixed-cut lyric reveal

![Japanese lyrics slide through invisible cuts from right to left](assets/slit-reveal.gif)

Each character slides into place before its first note. The default style puts
Sarasa UI J directly over the footage, then sweeps from off-white to amber.

```sh
python -m examples.slit_reveal build/slit-reveal.hook
```

[Source](../../examples/slit_reveal.py) · [Adapt the entrance to longer lyrics](../tutorials/karaoke-design.md#reveal-a-phrase-from-narrow-openings)

### Karaoke without a color wipe

![A small amber diamond hops between Chinese lyrics over a night street](assets/lyric-no-sweep.gif)

The diamond lands on the note attack and the glyph briefly grows. The whole
glyph turns amber at release. The preview uses Sarasa UI SC over a night street.

```sh
python -m examples.lyric_no_sweep build/lyric-no-sweep.hook
```

[Source](../../examples/lyric_no_sweep.py) · [Align motion with the notes](../tutorials/karaoke-design.md#mark-timing-without-a-color-wipe)

For more custom motion, see the [lyric studies](../tutorials/lyric-studies.md) on
timed copies, particle reveals, and curved trails.

## Karaoke count-ins

![An inline signal and separate star lamps count down to the lyrics](assets/karaoke-signals.gif)

The inline columns flash together. The stars clear one at a time above the
line. Both signals clear by the pickup. [Signal source](../../examples/karaoke_signals.py) · [Cue setup](../guides/text-and-cues.md)

### Paw countdown and character flips

Use `paw_countdown(step_seconds=...)` as a Track cue preset for four prints that
squash and vanish in step with the music. Use the built-in `spin_flip` exit with
`exit_unit="character"` to flip glyphs and their readings around their own pivots.
[Paw cue source](../../examples/paw_countdown.py) · [Entry and exit options](../guides/karaoke-effects.md#entry-and-exit)

## Add drawing and color

### Word backgrounds and decorations

![Measured lyric ranges with colored backgrounds, cue bars, and sparkles](assets/word-backgrounds.gif)

Draw backgrounds, cue bars, and sparkles against measured lyric ranges. Edit
the range, cue factory, or lifetime to attach the drawing to a different phrase.

```sh
python -m examples.scene_cues build/word-backgrounds.ass
```

[Source](../../examples/scene_cues.py)

### GPU gradient

![A pink-to-cyan gradient fills the moving lyric](assets/gpu-gradient.gif)

Export continuous shader color as `build/gpu-gradient.hook` alongside a plain
ASS version of the lyric.

```sh
python -m examples.gpu_gradient
```

[Source](../../examples/gpu_gradient.py) · [Render the hook](../guides/gpu-rendering.md)
