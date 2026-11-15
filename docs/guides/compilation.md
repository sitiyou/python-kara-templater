# Compilation, reports, and performance

Scene.compile returns a SceneResult containing the output Document, per-object
reports, event_count, peak_active, byte_count, estimated_events,
max_time_quantization, diagnostics, and generated event_origins. Preparation and
compilation preserve caller-owned source objects.

## Choose semantics before tuning cost

Static geometry and eligible linear motion use native ASS expressions. General
animation, references, masks, and materials are evaluated deterministically at
bounded intervals and declared breakpoints. Adjacent identical output can merge.
Use native_tweens=True explicitly for supported continuous Tween interpolation.

Native continuous interpolation and held samples can differ between sample
instants. Arbitrary callbacks have no automatic continuous error guarantee.
Increasing fps makes the sample interval smaller; it does not prove a bound
between those samples. ASS event boundaries use 10 ms units, limiting useful
sampling to 100 samples/s.

Track's native mode evaluates property/raster callbacks while preparing lowered
NativeEvents. Editable mode defers callbacks to Scene compilation. Coverage is a
separate explicit material contract. See [Tracks](tracks.md) and
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

Pass an explicit SceneBudget to compile when the intended effect requires more.
A budget failure does not silently reduce detail or sampling. Conservative
preflight can reject a declaration before invoking its callbacks. Final checks
also include retained subtitle content, serialized bytes, and active-event peaks.
Native provenance comments consume serialized event budget; event_count reports
generated Dialogue rather than comments.

RasterSettings separately limits pixel work, frames, output characters, and
spatial color error. Track native OutputSettings limits its preparation. Passing
one set of limits does not disable the other stages' checks.

## Read the reports

ObjectReport.strategy identifies native, sampled, affine-path, banded, or native
event output. Inspect events, sample_interval, peak_path_points, peak_bands,
peak_clip_points, and origin where applicable. Frontend PreparedTracks.layer_count
is preparation metadata, not the final Scene event count.

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
