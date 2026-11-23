# Animation and timing

Scene animation writes named VisualState channels. A Tween interpolates a
StatePatch; a StateFunction evaluates custom behavior. Geometry, masks, materials,
and references have separate typed extension protocols.

## Keep a cursor moving through a phrase

A flying mark that follows a word has two clocks to satisfy: when it must
reach each syllable boundary, and how its position changes between boundaries.
Obtain the timed positions from the [measured lyric line](tracks.md#attach-a-drawing-after-layout).
For two adjacent spans of equal width lasting 100 ms and 600 ms, straight
segments meet at the correct position but the speed drops sixfold in one frame.
Applying ease-in/ease-out to every segment instead makes the mark stop at every syllable.

For continuous flight, use the times and positions as knots of one phrase.
Choose a shared horizontal speed at each interior knot. For adjacent forward
speeds `a` and `b`, the harmonic mean `2*a*b/(a+b)` follows the slower note
through the join. At a stationary rest use zero. A cubic Bézier segment of
duration `dt` between positions `x0` and `x1` then has horizontal control
points `x0 + v0*dt/3` and `x1 - v1*dt/3`. Use the same units for speed and
duration. Choose height along the full phrase and let the plane bank with the
path tangent. Check consecutive frames around a short-to-long join, plus
the onset and release of a held note.

## A karaoke effect without per-character scheduling

The complete runnable [pulse and drift example](../../examples/lyric_pulse_drift.py)
uses the same rules for 250 ms and 2 s notes:

```python
from kara_templater import DriftOut, LyricRule, ScalePulse

animations = (
    LyricRule("character", "singing", ScalePulse(peak=1.06, peak_at=0.42)),
    LyricRule("character", "after_singing", DriftOut(), offset=0.14, duration=0.56),
)
```

Pass these rules to `Track.effects`. The pulse occupies each original singing
interval; its peak is 42% through that interval. Each character then waits 140 ms
after its final singing interval and departs over 560 ms. The engine supplies the
measured pivot, applies the same transform to highlight aliases, and reserves the
exit interval during layout. The pulse's default easing slows at the start, peak
and end. The fixed peak factor in this example is an artistic choice, not a claim
that short and held notes should always have equal emphasis.

For a custom exit, replace `DriftOut()` with a relative transform:

```python
from kara_templater import Transform, Vec2, smooth_rate

exit_motion = Transform(
    offset=lambda p: Vec2(24 * smooth_rate(p), -36 * p * p),
    scale=lambda p: 1 - 0.04 * smooth_rate(p),
    opacity=lambda p: 1 - smooth_rate(p),
)
```

The rule still owns timing; `p` runs from 0 to 1 over that rule's duration.
No object-tree traversal, absolute-position calculation or ASS keyframe generation
is needed. Built-ins and custom transforms use the same binding and evaluator.
The example's `--custom` option combines this exit with duration-aware emphasis.

This example also attaches a vertical fill gradient through `LyricGradient`.
Export scenes with gradients or custom motion as hooks.

## Change parameters for each singing interval

A fixed animation works without a factory. When parameters depend on note length,
use one context argument:

```python
from kara_templater import LyricAnimationContext, LyricRule, ScalePulse, smooth_rate

def pulse(timing: LyricAnimationContext) -> ScalePulse:
    return ScalePulse(
        peak=1 + 0.06 * smooth_rate(min(1, timing.duration / 0.6)),
        peak_at=0.42,
    )

rule = LyricRule("character", "singing", pulse)
```

The factory runs once for each resolved interval. A glyph sung for 250 ms and
then again for 1 s gets two independently chosen peaks; pauses are not included
in either duration. `timing.target` retains the full original singing history,
and `timing.line` provides measured geometry when needed. The returned animation
still uses the common normalized-progress interface and automatic lyric pivot.

`timing.interval` is the resolved absolute interval, including copy delay but
before rule offset/stagger. `timing.duration` uses an explicit rule duration when
provided, otherwise the interval length. Zero-length intervals report zero;
missing intervals do not call the factory. An enter/exit context has no absolute
interval before layout; reading its duration requires an explicit rule duration.
A factory may instead return a Timeline sequence with its own authored duration.

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
its peak at `peak_at` (default 0.5), then returns to the captured value. Each phase
uses `smooth_rate` by default. `smoother_rate` also makes acceleration zero at
the endpoints and pulse peak; pass `rate=linear_rate` for a triangular pulse. Its pivot
uses untransformed local coordinates and remains fixed under existing rotation,
scale and skew. Pivot compensation writes position as well as scale, so a
simultaneous position animation belongs on a parent or needs explicit composition.

When `pivot` is omitted, `LyricRule` resolves `ScalePulse`, `DriftOut` and
`Transform` to the measured target center, including inside animation sequences.
Character and ruby targets use their own undecorated layout boxes; syllable and
line targets use body-text centers so glow and ruby do not displace the axis.
Highlight/glow contributions share the target's axis. Direct Scene animations use
the local origin when the pivot is omitted. Pass `pivot=Vec2()` to explicitly use
the origin even in a lyric rule, or supply any other local point.

## Simple custom motion

Use `Transform` for relative motion defined by progress. It infers the written
channels, preserves incoming opacity and scale, and can combine motion and fade:

```python
from kara_templater import LyricRule, Transform, Vec2, smooth_rate

drift = Transform(
    offset=lambda p: Vec2(12 * p, -36 * p),
    scale=lambda p: 1 - 0.04 * smooth_rate(p),
    opacity=lambda p: 1 - smooth_rate(p),
)
departure = LyricRule(
    "character", "after_singing", drift, offset=0.16, duration=0.56,
)
```

For the built-in version, use
`LyricRule("character", "after_singing", DriftOut(), offset=0.16, duration=0.56)`
(import `DriftOut` from `kara_templater`). Its default smooth easing also applies
to travel; use `rate=linear_rate` for constant-speed travel/shrink/fade.

Add `departure` to `Track.effects`. `after_singing` starts at the selected
target's last singing end; `offset` adds the pause in seconds. Selecting `segment`
instead triggers after each repeated segment. The anchor requires an explicit
duration or a sequence's authored length; a zero-length singing span still has an
end, while a target without singing produces no animation.

`Transform` values can be constants or functions of normalized progress. Offset
adds parent-space pixels, rotation adds degrees, scale multiplies by a scalar or
Vec2, and opacity multiplies the incoming opacity. Constants apply throughout the
clip. Omitted values preserve state and write no channels. A local `pivot` can fix
a point during scaling/rotation before offset is added. Bind built-in and custom
animations with the same rules and compose them through the same Scene hierarchy.

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

Track.effects accepts LyricRule values alongside callable visual effects. Each rule selects line, syllable,
segment, character, ruby or cue targets and binds a common StateAnimation.
Enter/exit anchors refer to display boundaries; singing anchors retain original
source times. A callable anchor returns absolute TimeSpan values. Duration may
come from the singing interval, an authored AnimationSequence, or an explicit
positive duration on the rule.

`stagger` spaces selected targets in selection order. With `exit`, the last
target ends at the display end plus `offset`, and earlier targets finish earlier;
the allocator reserves the entire staggered interval. Other anchors add the
stagger to each target's own anchor. Thus `singing` with a nonzero stagger
deliberately delays later targets; omit it to follow source singing exactly.
`ScatterOut` supplies deterministic per-target drift/rotation using the common
relative transform. `CurveIn` supplies a quadratic entrance to the base pose.
See the [eight motion studies](../tutorials/lyric-studies.md) for composition with
copies, ruby, particles and custom trajectories.

Extending a line's display for an exit animation does not stretch keyframes
bound to singing. Their authored offsets stay anchored to the source, and held
values remain available during the tail. Required exit time occupies the layout
row; optional preview can shrink, but the allocator cannot silently cut the exit.

Timeline.animation freezes a reusable sequence. Bind it directly to an object or
return it from a lyric animation factory. Factories receive a `LyricAnimationContext` before layout, so the entire
sequence's occupancy can be reserved.

HighlightArrival selects measured character crossings. It supports named
highlights, first/each selection, repeat rounds and enter/center/complete
thresholds. A fixed rule duration can replace the default traversal duration.
The [lyric highlight tutorial](../tutorials/lyric-highlights.md) is a complete
example with character jumps and whole-line fades.

## Sampling and output semantics

ASS uses native transforms and hard clips. Custom motion callbacks require hook export.

`ScalePulse(rate=linear_rate)` can use native rectangle-clip lowering. With
`native_tweens=True`, `ScalePulse` and `DriftOut` using `smooth_rate` or `smoother_rate` can also use
the `native-clip-eased` strategy. Eligible cubic and
quintic scale phases use three or five standard ASS transforms instead of a long
list of scale samples. The compiler checks positive intermediate scale controls
and bounds millisecond phase rounding to 0.001 scale units; unsafe controls or
mixed unsupported scale curves retain the bounded piecewise form. Clip edges and
opacity retain their existing separate approximation. The compiler
subdivides the supported polynomial curve on the ASS time grid, bounding continuous error by
0.1 parent-space pixels per position coordinate, 0.001 per scale coordinate and
1/255 opacity. Native clip edge error/rounding is checked separately against the
approximated geometry; these are not final raster-pixel error guarantees.

This optimization requires held clips, grid-aligned original start/end times,
ordinary eligible rectangle clipping, and parents with no scale/rotation/skew or
animated geometry. A pulse peak can fall between grid points: source duration and
the original curve determine the approximation. If the bounds cannot be met at
10 ms resolution, ASS compilation raises SceneCompileError. Arbitrary custom curves
are not assumed to match either supported polynomial. Inspect output cost when applying animation to many glyphs.

Animation evaluation and conflict checks use the same 1e-10-second numerical
clock. Adjacent boundaries such as `0.1 + 0.2` and `0.3` denote the same instant;
held values reach their endpoints and released values restore at that boundary.
This numerical precision does not change ASS's 10 ms event grid.

Tween easing must return a finite value. Finite overshoot is allowed: color
interpolation clamps each RGB channel to 0–255, while geometric channels can
extrapolate. Other state constraints, such as opacity in 0–1 and nonnegative
border/blur, still apply to the resulting state.

For easing, use `linear_rate`, `smooth_rate`, `smoother_rate`, `ease_in`, `ease_out` or
`ease_in_out`. `there_and_back(peak_at=0.25, return_at=0.5, rise=ease_in,
fall=ease_out)` returns a reusable rate for Tween: rise during the first quarter,
hold until halfway, then return. These values are normalized progress, not
another time unit or animation schedule.

For eligible single-line top-left-aligned text with native rectangular clips,
the compiler may emit a centered ASS anchor. A centered pulse then uses scale
transforms without splitting events for compensating position changes. This is
an output-only change: source objects, measured pivots, masks and gradient
coordinates remain unchanged. Curved departures still need separate linear
movement sections. Inspect output
cost even when pulse events have been merged.

`DriftOut(travel_rate=linear_rate)` keeps displacement at constant speed while
its `rate` still eases shrink and opacity. With the default `travel_rate=None`,
all three follow `rate`. This separates motion design from fade/scale design;
choose it explicitly rather than silently changing a requested eased path.
For eligible native text, the compiler proves linear output-anchor motion over
all geometry knots and can combine it into one ASS move with scale/alpha
transforms. Arbitrary travel callbacks require hook export.

## Size and time relative to the lyric

A glyph has its own authored font size after reading style selection. A note
has a duration for each singing interval, including separate repeats of a
single character. Expressions use script pixels or seconds according to
their field. Reuse an expression as a Python value across tracks.

```python
from kara_templater import FadeOut, Glyph, KaraokeEffects, LyricRule, Note, ScalePulse

ink = KaraokeEffects.duotone(feather=Glyph.font_size / 8)
attack = LyricRule("character", "singing", ScalePulse(), duration=Note.duration / 2)
release = LyricRule("character", "after_singing", FadeOut(),
                    offset=(Note.duration / 4).clamp(0.06, 0.20), duration=0.18)
```

The attack uses half of each note. The release uses the target's final note
to set its hold time. Literal lengths and seconds stay fixed. A display anchor
or arbitrary callback interval has no identified note; using `Note.duration`
there raises an error during preparation. In a factory, `context.duration` is
the requested animation duration, and `context.resolve(Note.duration)` gives
the underlying note length. Use `Animation.duration` in an offset to refer to the resolved length (for
example, `offset=Animation.duration / 2`). Using that field to define the
duration itself raises a binding error. A glyph-target factory can also resolve
`Glyph.font_size`, and `Canvas.height` is available for resolution-relative lengths. Dimensions and note lengths are bound before layout
allocation, so seeking or exporting never re-evaluates author expressions.
