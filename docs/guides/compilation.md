# Compilation, reports, and performance

Scene.compile returns a SceneResult containing the output Document, per-object
reports, event_count, peak_active, byte_count, estimated_events,
max_time_quantization, diagnostics, and generated event_origins. Preparation and
compilation preserve caller-owned source objects.

## Choose semantics before tuning cost

Static geometry and eligible linear motion use native ASS expressions. General
animation, references, masks, and materials are evaluated deterministically at
bounded intervals and declared breakpoints. Adjacent identical output can merge.
Use `native_tweens=True` for continuous interpolation of supported tweens.
An eligible `FadeIn(rate=ease_out)` or `FadeOut(rate=ease_out)` also follows its
quadratic opacity curve at playback time, including on lyrics with a moving
rectangle wipe. Fill and outline still composite separately in libass, so their
overlap can be more opaque during a fade than a single faded image of the line.

For a top-level coverage group, this option also lowers a continuous linear
opacity curve from built-in Tween, FadeIn, FadeOut, or held sequences to ASS
alpha transforms after pixel composition. Geometry and materials still use
their sampled frames; reports identify this as coverage-native-opacity. Material
callbacks continue to see the original animated state. Nonlinear callbacks,
opacity jumps/resets, non-centisecond boundaries, parent groups, and explicit
per-material scope opacity retain sampled output. Native alpha interpolation
has 8-bit rounding and can differ from held samples between sample instants.
Both frame and total character budgets include the added transform tags.

Native continuous interpolation and held samples can differ between sample
instants. Arbitrary callbacks have no automatic continuous error guarantee.
Increasing fps makes the sample interval smaller; it does not prove a bound
between those samples. ASS event boundaries use 10 ms units, limiting useful
sampling to 100 samples/s.
Scene event boundaries round to the nearest centisecond, with exact half steps
rounding to the even centisecond. `max_time_quantization` reports the largest
boundary adjustment in seconds. This Scene policy does not change raw ASS
serialization.

`diagnostics` reports sampled animation intervals whose start and end round to
the same centisecond, including intervals between declared breakpoints. Messages
identify the owning object and absolute seconds; repeated child contributions
do not duplicate the same message. Compilation retains its sampling semantics
rather than extending the animation. Hidden intervals are excluded. Native
Tween transforms retain millisecond timing and do not receive this sampling
diagnostic. Undeclared peaks inside arbitrary callbacks cannot be detected by
this check; an entire lifetime that vanishes on the grid remains an error.

Track preparation resolves semantic anchors, layout and author factories into
ordinary objects. Frame callbacks run through the same Scene evaluator used for
direct objects. Coverage remains an explicit material contract. See [Tracks](tracks.md) and
[materials](materials.md) before comparing their output.

## Default Scene budgets

| Limit | Default |
| --- | --- |
| fps | 50 |
| max_events | 25,000 |
| max_bytes | 10 MiB |
| max_active | 1,000 |
| max_path_points | 4,096 |
| max_bands | 1,024 |
| max_boolean_work | 1,000,000 |
| clip_error_px | 0.75 pixels |

Pass an explicit SceneBudget to compile when the intended effect requires more.
A budget failure does not silently reduce detail or sampling. Conservative
preflight can reject a declaration before invoking its callbacks. Final checks
also include retained subtitle content, serialized bytes, and active-event peaks.
Native provenance comments consume serialized event budget; event_count reports
generated Dialogue rather than comments.

RasterSettings separately limits pixel work, frames, output characters, and
spatial color error. These limits supplement whole-scene budgets rather than
disabling final output checks.
For coverage output, these settings apply to each coverage group: max_output_chars
counts that group's generated event text. Use SceneBudget.max_bytes to limit the
complete serialized document, including all groups, styles, and retained sources.

## Read the reports

Pass `on_estimate` to Scene.compile or compile_scene to inspect a read-only
SceneEstimate after declaration/source validation and before frame callbacks.
Raise an exception from this callback to cancel; the exception propagates and
the input Scene and Document remain unchanged. Author factories run during
preparation, before this callback.

SceneEstimate.estimated_events covers ordinary/native output estimates only.
Its coverage tuple gives each group's planned frames (including breakpoints),
target_samples (frames times drawable leaves), and max_channel_error. Coverage
rectangle counts are unknown until rendering, so these counts are not a total
event estimate or a prediction of elapsed time or memory. Final budgets still
apply. The callback is not a way to mutate the compilation plan.

ObjectReport.strategy identifies native, sampled, affine-path, banded, or native
event output. Inspect events, sample_interval, peak_path_points, peak_bands,
peak_clip_points, and origin where applicable. LyricScene.plans provides layout
and binding metadata; object counts are not final event counts.

SceneCompileError identifies an object_id and optional EventOrigin. Lower-level
OutputCapabilityError can add origin/time metadata. Keep the exception cause and
source notes when reporting callback failures. SceneResult.event_origins refers
to actual generated Dialogue records; objects without lyric sources may have
origin=None. Source dependencies do not claim ownership of one singing interval.

## Reduce a costly effect

- Reuse simple geometry and limit simultaneously visible particles/echoes.
- Prefer native motion when its continuous semantics match the intended effect.
- Use a coarser explicit color-band step or simplify masks when visually acceptable.
- Reserve raster/coverage output for effects requiring those composition semantics.
- Separate source timing from display padding; extending a glow should not move
  the singing cursor.
- Inspect the actual saved ASS in the intended rendering environment.

The whole-song example deliberately uses larger limits. Its budget is an authored
choice for a dense 180-second fixture, not a suitable default for every subtitle.

Adjacent sampled events can merge when their encoded ASS content is identical.
This happens after evaluation: arbitrary callbacks still run at each required
sample. Different floating-point states may encode the same 8-bit alpha, while
visibility gaps prevent merging across the gap.
