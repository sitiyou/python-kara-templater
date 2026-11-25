# Design a song layout

Build a complete karaoke song layout step by step, starting from a single lead vocal and adding ruby readings, an upper harmony track, and a rhythmic count-in. Use this walkthrough whenever your song needs multiple singers or readings to stay clear on screen together.

## Start with a main vocal track

A single `Track` with `KaraokeEffects()` already handles most of a song's layout and transitions. By default, omitting `layout` selects `KaraokeRows()`, which alternates two bottom rows left and right.

At 1920 × 1080, `KaraokeRows()` leaves 50 px on each side, 60 px at the bottom, and 45 px between co-visible rows. Short lines shift inward together so their outer margins stay balanced, and all margins scale proportionally with canvas height (for example, 40 px bottom clearance at 720p).

`KaraokeEffects()` fades each line in and out over 0.30 s, pulses each active syllable, and wipes from white to coral. Each `Track` requests 5.0 s of preview before the first note and targets a 1.0 s tail after the last note (including the exit). When rows hand off tightly, the layout trims preview first, then hold time, and scales transitions only when needed.

For horizontal main vocals at 1080p, start around 100 px for the body font size and 45 px for ruby, scaling both with canvas height. Test the longest line and the densest readings at delivery resolution before locking sizes.

## Add ruby readings

Write readings inline with `body|reading` inside your timed lyrics, and define a `<StyleName>-furigana` style on the `Document`. The library measures body and ruby together so co-visible rows never collide.

By default, all readings on a line share a single horizontal baseline above the body with a 6 px hard-outline gap (`ruby_gap=6`). Give the ruby style a thinner outline than the body so small character counters stay open.

## Separate harmony onto its own track

Put backing vocals or a second singer on a second `Track` with its own `source` predicate and a top-anchored layout such as `KaraokeRows(rows=1, anchor="top")`. Keeping singers on separate tracks lets both share the same song clock while never fighting for the same rows.

Give harmony a smaller font size, a distinct highlight color, and calmer motion (such as `highlight="none"` for a steady wipe without bounce). That visual contrast lets viewers tell lead and harmony apart at a glance.

![Two main-vocal palettes with the same violet harmony over light and dark video](../examples/assets/track-themes.png)

## Add a rhythmic count-in

Use a count-in when a phrase starts after a silence and singers need a beat before the first note. Attach a `CueMarker` in the lyric text and bind its name in `Track.cues` with a `CuePreset`.

Choose the timing behavior before picking a symbol:

| Cue factory | Visual behavior | Placement |
| --- | --- | --- |
| `VolumeCue` | Columns flash together, then fill left to right | Inline beside the phrase |
| `SignalCue` | Vector lamps (`circle`, `star`, notes, or a custom `VectorPath`) extinguish one per step | Inline or above/below the line |
| `BarsCue` | Stepwise bars tick down toward the pickup | Inline or independent |
| `TextCue` | Numeric or custom labels (`3`, `2`, `1`) advance on each beat | Independent or inline |

![An inline signal and separate star lamps count down to the lyrics](../examples/assets/karaoke-signals.gif)

Match the count-in's stroke weight and palette to the lyrics it leads into. Check the first beat, a middle beat, and the final pickup frame over actual footage so the last step lands right on the first note. For a custom vector motif such as pulsing paw prints above the row, see [paw_countdown.py](../../examples/paw_countdown.py).

## Put the whole song together

This complete script combines a two-row lead track with ruby, an inline `VolumeCue` count-in, and a top-anchored harmony track, then writes `song-layout.hook`.

```python
from kara_templater import (
    Color,
    CueMarker,
    CuePreset,
    Document,
    KaraokeEffects,
    KaraokeRows,
    Line,
    Style,
    Track,
    VolumeCue,
    build_lyric_scene,
)

document = Document.create(
    width=1280,
    height=720,
    styles=(
        Style(name="Main", fontname="DejaVu Sans", fontsize=64, bold=True, outline=2.5, shadow=0),
        Style(name="Main-furigana", fontname="DejaVu Sans", fontsize=28, outline=1.2, shadow=0),
        Style(name="Harmony", fontname="DejaVu Sans", fontsize=38, bold=True, outline=1.5, shadow=0),
    ),
)

cue = CueMarker("intro", "count").markup()
document.records.extend(
    (
        Line(
            start_time=2500,
            end_time=5000,
            style="Main",
            text=cue + r"{\k50}Light|lait{\k50} up{\k150} the sky",
        ),
        Line(
            start_time=5200,
            end_time=7700,
            style="Main",
            text=r"{\k30}Take{\k30} my{\k60} hand{\k130} tonight",
        ),
        Line(
            start_time=5200,
            end_time=7700,
            style="Harmony",
            text=r"{\k120}Ah{\k130} ah",
        ),
    )
)

scene = build_lyric_scene(
    document,
    tracks=(
        Track(
            id="main",
            source=lambda source: source.style == "Main",
            cues={"count": CuePreset(factory=VolumeCue(), lead=2.0, duration=2.0)},
            effects=(KaraokeEffects(),),
        ),
        Track(
            id="harmony",
            source=lambda source: source.style == "Harmony",
            layout=KaraokeRows(rows=1, anchor="top"),
            effects=(
                KaraokeEffects(
                    highlight="none",
                    after_fill=Color.hex("#6AD4FF"),
                ),
            ),
        ),
    ),
)
scene.export("song-layout.hook")
```

To adapt this template to Japanese lyrics with furigana, swap `DejaVu Sans` for a CJK typeface (such as `Sarasa UI J` or `Noto Sans CJK JP`) and write readings like `{\k50}空|そら`.

## Tune placement and verify readability

If you need a fixed starting coordinate instead of automatic bottom margins, switch from `KaraokeRows` to `Layout(rows=2, position=Vec2(...))` inside an explicit `region=Box(...)`. `Layout` stacks rows downward from your chosen origin, spacing them by measured row height plus 20% of the largest body font size.

Before rendering the whole song, check three moments in Hook playback:

- A **short syllable** and a **held syllable** on both bright and dark video frames.
- A **dense row handoff** where a new phrase enters while the previous row is still finishing.
- The **count-in pickup** where the final cue step meets the first syllable.

> [!TIP]
> For a ready-made main-vocal style with a dark keyline, colored rim, and soft halo over changing footage, see [Built-in karaoke effects](../guides/karaoke-effects.md) and the multi-palette example [karaoke_designs.py](../../examples/karaoke_designs.py).

## Next steps

- [Effect recipes](effect-recipes.md) for stand-alone treatments such as slit reveals, no-wipe cues, and two-state outlines.
- [Lay out vocal tracks](../guides/tracks.md) for all `Track`, `KaraokeRows`, and `Layout` options.
- [Ruby readings and cues](../guides/text-and-cues.md) for cue timing with BPM, custom cue factories, and ruby alignment.
- [Choose and register fonts](../guides/fonts.md) for typeface selection and font registration.
