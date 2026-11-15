# Animation and timing

Scene animation writes named VisualState channels. A Tween interpolates a
StatePatch; a StateFunction evaluates custom behavior. Geometry, masks, materials,
and references have separate typed extension protocols.

## Time units

| Interface | Unit |
| --- | --- |
| Lifetime, AnimationClip, SceneTimeline, SceneEvaluator | Seconds |
| StateKeyframe and geometry/mask callback local time | Seconds |
| StateReference callbacks and StateLookup times | Absolute Scene seconds |
| Composition, Timeline.play, TimeSpan, sampled Animation function time | Seconds |
| Track Animate duration/offset, fades, On events, Pulse duration | Milliseconds |
| KaraokeItem window, Segment, Line, low-level TimeRef and property clocks | Milliseconds |
| ASS serialization and generated event boundaries | Centiseconds: 10 ms |

AnimationContext.syllable and next_syllable return TimeSpan values in seconds,
while the corresponding event's start/end fields are milliseconds. Convert at
these boundaries explicitly.

## Scene clips and timelines

An AnimationClip has a nonnegative start relative to the object's birth, a
positive duration, an animation, and optional breakpoints. Breakpoints are seconds
from the clip's start. The final value is held by default; `hold=False` releases
the written channels after the clip ends. Overlapping writes to the same channel
are rejected instead of depending on incidental evaluation order.

Use SceneTimeline.play for sequential or simultaneous animation, stagger for
repeated offsets, repeat for repeated schedules, and keyframes for explicit
state targets. Assign the resulting `timeline.clips` to the object's animations.
Each parallel animation must write compatible channels. Repeats and copies keep
local clocks and declared discontinuities.

A StateFunction receives the incoming state and normalized progress. Declare
exactly the channels it writes. Its result must depend on its arguments and
stable configuration, not a previously rendered frame or mutable random stream.
The [custom animation tutorial](../tutorials/custom-animation.md) is complete and
runnable. Declare discontinuities with breakpoints so sampling does not place
them between arbitrary frame centers.

## Track events and reusable animation

Track accepts Animation instances. On binds an Animate declaration to
Display.Start, Display.End, Syllable.Singing, or SegmentSinging. Animate changes
scale, opacity, offsets, or supported material properties. Envelope describes
attack/release behavior; Sequence and Parallel combine declarations.

Subclass Animation and use `@on(...)` when you need event-specific logic. A
sampled Animation function receives local seconds and AnimationContext and
returns a sparse Transform. Composition with Timeline provides a sequential
seconds-based authoring interface. None of these callbacks need compiler
subclasses or generated ASS tags.

SingingPulseAnimation grows a syllable around its singing interval.
HighlightAnimation applies property functions to independently drawable
characters using Pulse arrival clocks. Pulse controls threshold, traversal or
fixed millisecond duration, named/first/each highlight selection, and retriggering.
With no explicit properties, HighlightAnimation uses the trigger's scale pulse.
Optional TextRange values limit the affected source ranges. For example:

```python
from math import pi, sin
from kara_templater import HighlightAnimation, Pulse

character_arc = HighlightAnimation(
    trigger=Pulse(duration_ms=400),
    offset_y=lambda progress: -24 * sin(pi * progress),
)
```

Add `character_arc` to a Track's animations. It schedules each character at its
own arrival, leaving the lyric's singing segments unchanged.

## Sampling and output semantics

Native Track output can use continuous ASS transforms. Editable Scene output
holds deterministic samples unless an eligible native strategy is chosen.
`native_tweens=True` explicitly permits eligible continuous Tween lowering.
These choices can differ between sample instants. Custom callbacks do not gain
a proven continuous error bound simply from a sampling rate. Inspect strategy
and sample_interval in [compilation reports](compilation.md).
