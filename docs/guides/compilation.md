# ASS compilation, reports, and performance

These reports describe standard ASS event generation. For standalone shaders
and playback options, see [Choose an output](choosing-output.md).

Scene.ass.compile returns a AssResult containing the output Document, per-object
reports, event_count, peak_active, byte_count, estimated_events,
max_time_quantization, diagnostics, and generated event_origins. Preparation and
compilation preserve caller-owned source objects.

## Choose semantics before tuning cost

Static geometry, moves, supported tweens and rectangle keyframes lower to ASS tags.
Frame sampling, gradients and feather strips raise SceneCompileError.

Scene event boundaries round to the nearest centisecond, with exact half steps
rounding to the even centisecond. `max_time_quantization` reports the largest
boundary adjustment in seconds. This Scene policy does not change raw ASS
serialization.

## Default Scene budgets

| Limit | Default |
| --- | --- |
| max_events | 25,000 |
| max_bytes | 10 MiB |
| max_active | 1,000 |
| max_path_points | 4,096 |
| max_boolean_work | 1,000,000 |
| clip_error_px | 0.75 pixels |

Pass an explicit AssBudget to compile when the intended effect requires more.
A budget failure does not silently reduce detail or sampling. Conservative
preflight can reject a declaration before invoking its callbacks. Final checks
also include retained subtitle content, serialized bytes, and active-event peaks.
Native provenance comments consume serialized event budget; event_count reports
generated Dialogue rather than comments.

## Read the reports

`on_estimate` receives the estimated event count before serialization.
Each object report identifies the lowering strategy, generated event count and
source origin. Event budgets also apply to scenes with many native objects.
