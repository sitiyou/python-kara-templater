# Tutorials

Step-by-step walkthroughs for building karaoke templates, from a full song layout to custom highlight motion and reusable animations. Start with a short phrase that has both a quick note and a held note, then play the exported Hook before scaling up to a whole song.

## Choose a tutorial by goal

| Goal | Tutorial | What you build |
| --- | --- | --- |
| Lay out lead vocals, ruby, harmony, and count-ins | [Design a song layout](karaoke-design.md) | A multi-track song template with alternating rows, readings, and a rhythmic cue |
| Trigger motion as the sweep reaches each character | [Animate the highlight](lyric-highlights.md) | Character jumps timed to the highlight sweep front |
| Write your own motion curve in Python and GLSL | [Write a custom animation](custom-animation.md) | A reusable factory that sends spinning sparks along a wave |
| Build a specific visual treatment | [Effect recipes](effect-recipes.md) | Stand-alone recipes for no-wipe cues, slit reveals, focus fades, typing, two-state outlines, and shattering glyphs |
| Compare eight animation patterns on one lyric | [Motion studies](lyric-studies.md) | Side-by-side studies of pulses, copies, particles, trails, and independent clocks |

## Recommended order

1. Start with [Design a song layout](karaoke-design.md) to set up tracks, alternating rows, ruby readings, and count-ins with library defaults.
2. Browse [Effect recipes](effect-recipes.md) when you want a specific visual treatment such as a slit reveal, a no-wipe marker, or distinct before-and-after outlines.
3. Work through [Animate the highlight](lyric-highlights.md) when a character or accent must react at the exact moment the sweep passes through it.
4. Read [Write a custom animation](custom-animation.md) when built-in animations are not enough and you want a reusable custom curve that runs in a Hook.
5. Finish with [Motion studies](lyric-studies.md) to compare how rules, echoes, particles, and independent ornaments combine on short and held notes.

> [!TIP]
> Test every new template on a 5-second clip that contains one fast syllable, one held syllable, and one row handoff. Checking timing on a short clip saves time before rendering a full song.

## Next steps

- [Quickstart](../getting-started.md) to install the library and export your first Hook.
- [Core concepts](../concepts.md) for the mental model behind `Document`, `Track`, and `Scene`.
- [Example scripts](../examples/README.md) to run finished templates from a checkout.
