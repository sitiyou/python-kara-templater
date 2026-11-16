# Animation and timing

Scene animation writes named VisualState channels. A Tween interpolates a
StatePatch; a StateFunction evaluates custom behavior. Geometry, masks, materials,
and references have separate typed extension protocols.

## Time units

| Interface | Unit |
| --- | --- |
| Lifetime, AnimationClip, Timeline, SceneEvaluator | Seconds |
| StateKeyframe and geometry/mask callback local time | Seconds |
| StateReference callbacks and StateLookup times | Absolute Scene seconds |
| Timeline.play, TimeSpan, AnimationSequence | Seconds |
| Track preview/tail, LyricRule offset/duration and semantic anchors | Seconds |
| KaraokeItem window, Segment, Line | Milliseconds |
| ASS serialization and generated event boundaries | Centiseconds: 10 ms |

## Scene clips and timelines

An object's `lifetime` controls visibility. Local callbacks normally measure time
from its start. Set `clock_start` to retain an earlier absolute origin when
cropping visibility: an object visible during `Lifetime(2, 3)` with
`clock_start=1` evaluates local time 1.5 at absolute second 2.5. `time_origin`
reports the effective origin. State animations, paint, geometry, masks and
coverage callbacks share it; references continue using absolute seconds.
The origin must be nonnegative and no later than the display end. Visibility
may also begin before the origin: `Lifetime(0.5, 3)` with `clock_start=1`
passes local time -0.25 to geometry, paint and mask callbacks at second 0.75.
Callbacks used with such windows must handle negative local seconds. Scheduled
state animations remain unstarted before their clip start; the clock is neither
clamped nor restarted. A delayed copy shifts both the display window and an explicit origin. Animations and
breakpoints may precede visibility, but cannot extend beyond its end.

Custom geometry, paint, glow, coverage partitions and scope opacity may declare
signed local breakpoints. Owning objects validate their absolute times against
Scene zero and the display end. Paint activity and a glow's `required_interval`
use the same signed clock; activity describes when a material changes, whereas
`required_interval` reserves visibility during lyric layout. Ordinary animation
clip starts, including `GlowFunction.from_animation`, remain nonnegative local
offsets from the chosen origin.

An AnimationClip has a nonnegative start relative to the object's birth, a
positive duration, an animation, and optional breakpoints. Breakpoints are seconds
from the clip's start. The final value is held by default; `hold=False` releases
the written channels after the clip ends. Overlapping writes to the same channel
are rejected instead of depending on incidental evaluation order.

Use Timeline.play for sequential or simultaneous animation, stagger for
repeated offsets, repeat for repeated schedules, and keyframes for explicit
state targets. Assign the resulting `timeline.clips` to the object's animations.
Each parallel animation must write compatible channels. Repeats and copies keep
local clocks and declared discontinuities.

FadeIn, FadeOut, Jump and ScalePulse use the same animation protocol on text,
paths, groups and lyric targets. ScalePulse multiplies the captured scale, reaches
its peak halfway through the clip, then returns to the captured value. Its pivot
uses untransformed local coordinates and remains fixed under existing rotation,
scale and skew. Pivot compensation writes position as well as scale, so a
simultaneous position animation belongs on a parent or needs explicit composition.

A StateFunction receives the incoming state and normalized progress. Declare
exactly the channels it writes. Its result must depend on its arguments and
stable configuration, not a previously rendered frame or mutable random stream.
Return a VisualState with Color paint values and Vec2 vector values. Invalid
callback results fail at evaluation with a contract error; Scene diagnostics
include the affected object and sample time. Binding a rule does not evaluate
its state callback, and compilation rejects an insufficient preflight budget
before sampling callbacks.
The [custom animation tutorial](../tutorials/custom-animation.md) is complete and
runnable. Declare discontinuities with breakpoints so sampling does not place
them between arbitrary frame centers.

## Lyric bindings and reusable animation

Track.animations accepts LyricRule values. Each rule selects line, syllable,
segment, character, ruby or cue targets and binds a common StateAnimation.
Enter/exit anchors refer to display boundaries; singing anchors retain original
source times. A callable anchor returns absolute TimeSpan values. Duration may
come from the singing interval, an authored AnimationSequence, or an explicit
positive duration on the rule.

Extending a line's display for an exit animation does not stretch keyframes
bound to singing. Their authored offsets stay anchored to the source, and held
values remain available during the tail. Required exit time occupies the layout
row; optional preview can shrink, but the allocator cannot silently cut the exit.

Timeline.animation freezes a reusable sequence. Bind it directly to an object or
return it from a lyric animation factory. Factories receive the measured line and
target before layout, so the entire sequence's occupancy can be reserved.

HighlightArrival selects measured character crossings. It supports named
highlights, first/each selection, repeat rounds and enter/center/complete
thresholds. A fixed rule duration can replace the default traversal duration.
The [lyric highlight tutorial](../tutorials/lyric-highlights.md) is a complete
example with character jumps and whole-line fades.

## Sampling and output semantics

Lyrics and direct Scene objects use the same compiler strategies. General
animation holds deterministic samples unless an eligible native strategy is chosen.
`native_tweens=True` explicitly permits eligible continuous Tween lowering.
These choices can differ between sample instants. Custom callbacks do not gain
a proven continuous error bound simply from a sampling rate. Inspect strategy
and sample_interval in [compilation reports](compilation.md).

Animation evaluation and conflict checks use the same 1e-10-second numerical
clock. Adjacent boundaries such as `0.1 + 0.2` and `0.3` denote the same instant;
held values reach their endpoints and released values restore at that boundary.
This numerical precision does not change ASS's 10 ms event grid.

Tween easing must return a finite value. Finite overshoot is allowed: color
interpolation clamps each RGB channel to 0–255, while geometric channels can
extrapolate. Other state constraints, such as opacity in 0–1 and nonnegative
border/blur, still apply to the resulting state.

For easing, use `linear_rate`, `smooth_rate`, `ease_in`, `ease_out` or
`ease_in_out`. `there_and_back(peak_at=0.25, return_at=0.5, rise=ease_in,
fall=ease_out)` returns a reusable rate for Tween: rise during the first quarter,
hold until halfway, then return. These values are normalized progress, not
another time unit or animation schedule.
