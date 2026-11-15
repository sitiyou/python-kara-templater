# Animation and choreography

Pure state/property animation and typed event composition. Scene and composition clocks use seconds; Track Animate/event/property intervals use milliseconds. See the [time-unit table](../guides/animation.md).

[All public symbols](README.md#symbol-index)

## Contents

- [Animate](#animate)
- [AnimatedProperties](#animatedproperties)
- [Animation](#animation)
- [AnimationClip](#animationclip)
- [AnimationContext](#animationcontext)
- [AnimationEvent](#animationevent)
- [AnimationResult](#animationresult)
- [AnimationTarget](#animationtarget)
- [Channel](#channel)
- [Composition](#composition)
- [CompositionMode](#compositionmode)
- [Contextual](#contextual)
- [Display](#display)
- [Envelope](#envelope)
- [FadeInAnimation](#fadeinanimation)
- [FadeOutAnimation](#fadeoutanimation)
- [HighlightAnimation](#highlightanimation)
- [Keyframe](#keyframe)
- [Keyframes](#keyframes)
- [Milliseconds](#milliseconds)
- [MoveTo](#moveto)
- [On](#on)
- [OpacityTo](#opacityto)
- [Parallel](#parallel)
- [ProgressMode](#progressmode)
- [PropertyContext](#propertycontext)
- [PropertyTarget](#propertytarget)
- [PropertyValue](#propertyvalue)
- [RateFunction](#ratefunction)
- [ScaleTo](#scaleto)
- [SceneTimeline](#scenetimeline)
- [SegmentSinging](#segmentsinging)
- [Sequence](#sequence)
- [SingingPulseAnimation](#singingpulseanimation)
- [StateAnimation](#stateanimation)
- [StateFunction](#statefunction)
- [StateKeyframe](#statekeyframe)
- [StatePatch](#statepatch)
- [Syllable](#syllable)
- [TimeInterval](#timeinterval)
- [TimeRef](#timeref)
- [TimeSpan](#timespan)
- [Timeline](#timeline)
- [Transform](#transform)
- [TransformTo](#transformto)
- [Transition](#transition)
- [Tween](#tween)
- [VisualState](#visualstate)
- [display](#display)
- [ease_in](#ease_in)
- [ease_in_out](#ease_in_out)
- [ease_out](#ease_out)
- [linear](#linear)
- [linear_rate](#linear_rate)
- [on](#on)
- [singing](#singing)
- [smooth](#smooth)
- [smooth_rate](#smooth_rate)
- [there_and_back](#there_and_back)

## Animate

A sparse Track event animation declaration for geometry or material properties.

Duration and offset are milliseconds; sampled functions receive normalized
progress, and bounds declare costly material extents.

[Source](../../kara_templater/motion.py#L256)

```python
Animate(
    target: AnimationTarget | None = None,
    *,
    scale: PropertyValue | Envelope | Literal[StyleKeyword.UNSET] = StyleKeyword.UNSET,
    opacity: PropertyValue | Envelope | Literal[StyleKeyword.UNSET] = StyleKeyword.UNSET,
    offset_x: PropertyValue | Envelope | Literal[StyleKeyword.UNSET] = StyleKeyword.UNSET,
    offset_y: PropertyValue | Envelope | Literal[StyleKeyword.UNSET] = StyleKeyword.UNSET,
    fill: ColorValue | Literal[StyleKeyword.UNSET] = StyleKeyword.UNSET,
    stroke: ColorValue | Literal[StyleKeyword.UNSET] = StyleKeyword.UNSET,
    stroke_width: PropertyValue | Envelope | Literal[StyleKeyword.UNSET] = StyleKeyword.UNSET,
    blur_color: ColorValue | Literal[StyleKeyword.UNSET] = StyleKeyword.UNSET,
    blur_radius: PropertyValue | Envelope | Literal[StyleKeyword.UNSET] = StyleKeyword.UNSET,
    blur_width: PropertyValue | Envelope | Literal[StyleKeyword.UNSET] = StyleKeyword.UNSET,
    blur_opacity: PropertyValue | Envelope | Literal[StyleKeyword.UNSET] = StyleKeyword.UNSET,
    bounds: PaintBounds | None = None,
    duration: Milliseconds | None = None,
    offset: int = 0,
    rate: RateFunction = linear,
    keep: bool = False,
    compose: CompositionMode = 'replace',
)
```

## AnimatedProperties

The typed sparse geometry properties accepted by low-level Track behavior declarations.

Omitted properties do not write or reset unrelated channels.

[Source](../../kara_templater/properties.py#L428)

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `scale` | `PropertyValue` | `optional key` |
| `opacity` | `PropertyValue` | `optional key` |
| `offset_x` | `PropertyValue` | `optional key` |
| `offset_y` | `PropertyValue` | `optional key` |

## Animation

A reusable Track animation implemented by a typed sample function or @on event handlers.

Sampled time and duration are seconds; event declarations are resolved to source
targets before compilation.

[Source](../../kara_templater/motion.py#L519)

```python
Animation(
    function: Callable[[float, AnimationContext], Transform] | None = None,
    *,
    duration: float | None = None,
    extend_display: bool = False,
    hold: bool = False,
)
```

### Animation.actions

Yield typed event-bound declarations from this animation and its inherited handlers.

```python
Animation.actions(
    context: AnimationContext,
) -> Iterable[tuple[AnimationEvent, AnimationResult]]
```

### Animation.bind

Resolve this animation against the source context without changing the original lyric.

```python
Animation.bind(
    context: AnimationContext,
) -> tuple[MotionRule | MaterialRule, ...]
```

### Animation.sample

Evaluate local seconds, independently of previously sampled frames.

Without a function or override this raises NotImplementedError.
Event-only animations use bind() instead.

```python
Animation.sample(
    t: float,
    context: AnimationContext,
) -> Transform
```

## AnimationClip

A positive-duration state animation starting at local seconds from object birth.

hold retains final written channels; breakpoints are offsets from the clip
start.

[Source](../../kara_templater/scene_animation.py#L239)

```python
AnimationClip(
    start: float,
    duration: float,
    animation: StateAnimation,
    hold: bool = True,
    breakpoints: tuple[float, ...] = (),
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `start` | `float` | `required` |
| `duration` | `float` | `required` |
| `animation` | `StateAnimation` | `required` |
| `hold` | `bool` | `True` |
| `breakpoints` | `tuple[float, ...]` | `()` |

### AnimationClip.end

The local clip start plus duration, in seconds.

Type: `float`.

## AnimationContext

A Track item, current event, and local composition clock.

syllable/next_syllable expose seconds-based TimeSpan values while event fields
retain milliseconds.

[Source](../../kara_templater/motion.py#L167)

```python
AnimationContext(
    item: KaraokeItem,
    event: AnimationEvent | None = None,
    origin: float = 0.0,
    duration: float = 0.0,
    initial: Transform = Transform(scale=1, opacity=1, offset_x=0, offset_y=0),
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `item` | `KaraokeItem` | `required` |
| `event` | `AnimationEvent \| None` | `None` |
| `origin` | `float` | `0.0` |
| `duration` | `float` | `0.0` |
| `initial` | `Transform` | `Transform(scale=1, opacity=1, offset_x=0, offset_y=0)` |

### AnimationContext.events

Enumerate supported display, syllable, or segment events from the original source clocks.

```python
AnimationContext.events(
    event_type: type[E],
) -> Iterator[E]
```

### AnimationContext.next_syllable

Return the following source syllable interval in local seconds, or None if unavailable.

Type: `TimeSpan \| None`.

### AnimationContext.syllable

Return the selected source syllable interval as local seconds.

A single timed syllable is required.

Type: `TimeSpan`.

### AnimationContext.target

Return the current event target; raise when the context is not event-bound.

Type: `AnimationTarget`.

## AnimationEvent

A resolved Track trigger with target, millisecond start/end, source index, and display window.

Subclasses identify singing or display events.

[Source](../../kara_templater/motion.py#L73)

```python
AnimationEvent(
    target: AnimationTarget,
    start: Milliseconds,
    end: Milliseconds,
    index: int,
    window: DisplayWindow,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `target` | `AnimationTarget` | `required` |
| `start` | `Milliseconds` | `required` |
| `end` | `Milliseconds` | `required` |
| `index` | `int` | `required` |
| `window` | `DisplayWindow` | `required` |

## AnimationResult

Public type alias:

```python
type AnimationResult = Animate | Parallel | Sequence
```

## AnimationTarget

A stable source item and unit/segment selection for a Track animation.

kind determines whether the transform affects a group, syllable, reading, or
segment.

[Source](../../kara_templater/motion.py#L39)

```python
AnimationTarget(
    item_id: str,
    units: tuple[int, ...],
    kind: Literal['group', 'syllable', 'ruby', 'segment'] = 'syllable',
    segments: tuple[tuple[int, int], ...] | None = None,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `item_id` | `str` | `required` |
| `units` | `tuple[int, ...]` | `required` |
| `kind` | `Literal['group', 'syllable', 'ruby', 'segment']` | `'syllable'` |
| `segments` | `tuple[tuple[int, int], ...] \| None` | `None` |

## Channel

Public type alias:

```python
type Channel = Literal['position', 'scale', 'rotation', 'skew', 'opacity', 'fill', 'outline', 'border', 'blur', 'shadow']
```

## Composition

An animation built by recording child animations on a local timeline.

[Source](../../kara_templater/choreography.py#L122)

```python
Composition(
    builder: Callable[[Timeline, AnimationContext], None] | None = None,
    *,
    extend_display: bool = False,
    hold: bool = True,
)
```

### Composition.actions

Yield typed event-bound declarations from this animation and its inherited handlers.

```python
Composition.actions(
    context: AnimationContext,
) -> Iterable[tuple[AnimationEvent, AnimationResult]]
```

### Composition.bind

Resolve the composed schedule into Track property declarations with source-local timing.

```python
Composition.bind(
    context: AnimationContext,
) -> tuple[MotionRule | MaterialRule, ...]
```

### Composition.compose

Override to schedule seconds-based child animations on the supplied Timeline.

```python
Composition.compose(
    timeline: Timeline,
    context: AnimationContext,
) -> None
```

### Composition.sample

Evaluate this composition at local seconds and return a sparse Transform.

```python
Composition.sample(
    t: float,
    context: AnimationContext,
) -> Transform
```

## CompositionMode

Public type alias:

```python
type CompositionMode = Literal['replace', 'override', 'add', 'multiply']
```

## Contextual

Explicit opt-in to target/time context instead of a scalar progress.

[Source](../../kara_templater/properties.py#L61)

```python
Contextual(
    function: Callable[[PropertyContext], float],
    seed: int = 0,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `function` | `Callable[[PropertyContext], float]` | `required` |
| `seed` | `int` | `0` |

### Contextual.__call__

Evaluate the scalar function using the full PropertyContext rather than progress alone.

```python
Contextual.__call__(
    context: PropertyContext,
) -> float
```

## Display

Namespace for display Start and End events.

These refer to original visibility boundaries, independently of optional
animation extensions.

[Source](../../kara_templater/motion.py#L94)

```python
Display()
```

### Display.Start

Original display start, independent of animation window extensions.

[Source](../../kara_templater/motion.py#L101)

```python
Display.Start(
    target: AnimationTarget,
    start: Milliseconds,
    end: Milliseconds,
    index: int,
    window: DisplayWindow,
)
```

#### Fields

| Name | Type | Default |
| --- | --- | --- |
| `target` | `AnimationTarget` | `required` |
| `start` | `Milliseconds` | `required` |
| `end` | `Milliseconds` | `required` |
| `index` | `int` | `required` |
| `window` | `DisplayWindow` | `required` |

### Display.End

Original display end.

[Source](../../kara_templater/motion.py#L104)

```python
Display.End(
    target: AnimationTarget,
    start: Milliseconds,
    end: Milliseconds,
    index: int,
    window: DisplayWindow,
)
```

#### Fields

| Name | Type | Default |
| --- | --- | --- |
| `target` | `AnimationTarget` | `required` |
| `start` | `Milliseconds` | `required` |
| `end` | `Milliseconds` | `required` |
| `index` | `int` | `required` |
| `window` | `DisplayWindow` | `required` |

## Envelope

A scale envelope with a peak and millisecond attack/release durations.

Rise and fall functions receive normalized progress.

[Source](../../kara_templater/properties.py#L440)

```python
Envelope(
    *,
    peak: float = 1.1,
    attack: int = 80,
    release: int = 160,
    rise: Callable[[float], float] = linear,
    fall: Callable[[float], float] = linear,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `peak` | `float` | `1.1` |
| `attack` | `int` | `80` |
| `release` | `int` | `160` |
| `rise` | `Callable[[float], float]` | `linear` |
| `fall` | `Callable[[float], float]` | `linear` |

### Envelope.fall

Return normalized progress unchanged for linear interpolation.

```python
Envelope.fall(
    p: float,
) -> float
```

### Envelope.rise

Return normalized progress unchanged for linear interpolation.

```python
Envelope.rise(
    p: float,
) -> float
```

## FadeInAnimation

Fade a Track group from transparent to opaque after display start.

duration is milliseconds and rate receives normalized progress.

[Source](../../kara_templater/motion.py#L674)

```python
FadeInAnimation(
    *,
    duration: Milliseconds = 400,
    rate: RateFunction = linear,
)
```

### FadeInAnimation.actions

Enumerate declarations for matching source events without changing the source clocks.

```python
FadeInAnimation.actions(
    context: AnimationContext,
) -> Iterable[tuple[AnimationEvent, AnimationResult]]
```

### FadeInAnimation.bind

Resolve the configured event declaration into Track motion and material rules.

```python
FadeInAnimation.bind(
    context: AnimationContext,
) -> tuple[MotionRule | MaterialRule, ...]
```

### FadeInAnimation.sample

Evaluate local seconds, independently of previously sampled frames.

Without a function or override this raises NotImplementedError.
Event-only animations use bind() instead.

```python
FadeInAnimation.sample(
    t: float,
    context: AnimationContext,
) -> Transform
```

## FadeOutAnimation

Fade a Track group to transparent ending at display end.

duration is milliseconds and the declaration starts that duration before the
end.

[Source](../../kara_templater/motion.py#L688)

```python
FadeOutAnimation(
    *,
    duration: Milliseconds = 200,
    rate: RateFunction = linear,
)
```

### FadeOutAnimation.actions

Enumerate declarations for matching source events without changing the source clocks.

```python
FadeOutAnimation.actions(
    context: AnimationContext,
) -> Iterable[tuple[AnimationEvent, AnimationResult]]
```

### FadeOutAnimation.bind

Resolve the configured event declaration into Track motion and material rules.

```python
FadeOutAnimation.bind(
    context: AnimationContext,
) -> tuple[MotionRule | MaterialRule, ...]
```

### FadeOutAnimation.sample

Evaluate local seconds, independently of previously sampled frames.

Without a function or override this raises NotImplementedError.
Event-only animations use bind() instead.

```python
FadeOutAnimation.sample(
    t: float,
    context: AnimationContext,
) -> Transform
```

## HighlightAnimation

Animate drawable characters at a highlight or syllable trigger.

``trigger`` controls threshold, duration in milliseconds, and retriggering.
Properties receive normalized progress, including traversal across pauses.
With no properties, apply a scale pulse using ``trigger.scale``. Optional
ranges select source text; layout validates their drawable cluster bounds.

[Source](../../kara_templater/motion.py#L730)

```python
HighlightAnimation(
    *,
    trigger: Pulse = Pulse(trigger=HighlightEnter(threshold='enter'), target='triggering_char', pivot='char_center', scale=1.1, duration_ms='traversal', tracks='first', track_id=None, retrigger=True),
    ranges: tuple[TextRange, ...] | None = None,
    keep: bool = False,
    compose: CompositionMode = 'replace',
    scale: PropertyValue | Literal[StyleKeyword.UNSET] = StyleKeyword.UNSET,
    opacity: PropertyValue | Literal[StyleKeyword.UNSET] = StyleKeyword.UNSET,
    offset_x: PropertyValue | Literal[StyleKeyword.UNSET] = StyleKeyword.UNSET,
    offset_y: PropertyValue | Literal[StyleKeyword.UNSET] = StyleKeyword.UNSET,
)
```

### HighlightAnimation.actions

Yield typed event-bound declarations from this animation and its inherited handlers.

```python
HighlightAnimation.actions(
    context: AnimationContext,
) -> Iterable[tuple[AnimationEvent, AnimationResult]]
```

### HighlightAnimation.bind

Bind character rules without measuring text or evaluating callbacks.

```python
HighlightAnimation.bind(
    context: AnimationContext,
) -> tuple[MotionRule | MaterialRule, ...]
```

### HighlightAnimation.sample

Evaluate local seconds, independently of previously sampled frames.

Without a function or override this raises NotImplementedError.
Event-only animations use bind() instead.

```python
HighlightAnimation.sample(
    t: float,
    context: AnimationContext,
) -> Transform
```

## Keyframe

A scalar target at a normalized fraction or millisecond TimeRef with an incoming easing curve.

Resolution binds it to the selected interval.

[Source](../../kara_templater/properties.py#L338)

```python
Keyframe(
    at: float | TimeRef,
    value: float,
    rate: Callable[[float], float] = linear,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `at` | `float \| TimeRef` | `required` |
| `value` | `float` | `required` |
| `rate` | `Callable[[float], float]` | `linear` |

### Keyframe.rate

Return normalized progress unchanged for linear interpolation.

```python
Keyframe.rate(
    p: float,
) -> float
```

## Keyframes

Ordered scalar keyframes for a property interval.

Use explicit TimeRef values when targets depend on singing or display anchors.

[Source](../../kara_templater/properties.py#L359)

```python
Keyframes(
    *frames: Keyframe,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `frames` | `tuple[Keyframe, ...]` | `required` |

### Keyframes.resolve

Resolve normalized fractions or TimeRef anchors to the selected millisecond property interval.

```python
Keyframes.resolve(
    interval: tuple[float, float],
    segments: tuple[Segment, ...],
    window: DisplayWindow,
    *,
    progress: ProgressMode = 'envelope',
) -> tuple[tuple[float, float, Callable[[float], float]], ...]
```

## Milliseconds

Public type alias:

```python
type Milliseconds = int
```

## MoveTo

Offsets in layout pixels, relative to the unanimated target.

[Source](../../kara_templater/choreography.py#L215)

```python
MoveTo(
    *,
    x: float | None = None,
    y: float | None = None,
    duration: float | None = None,
    rate: RateFunction = linear,
)
```

### MoveTo.actions

Yield typed event-bound declarations from this animation and its inherited handlers.

```python
MoveTo.actions(
    context: AnimationContext,
) -> Iterable[tuple[AnimationEvent, AnimationResult]]
```

### MoveTo.bind

Resolve this animation against the source context without changing the original lyric.

```python
MoveTo.bind(
    context: AnimationContext,
) -> tuple[MotionRule | MaterialRule, ...]
```

### MoveTo.sample

Interpolate the configured sparse geometry target at local seconds.

```python
MoveTo.sample(
    t: float,
    context: AnimationContext,
) -> Transform
```

## On

Bind an Animate, Sequence, or Parallel declaration to a selected Track event type.

Optional source filtering and display extension are explicit.

[Source](../../kara_templater/motion.py#L636)

```python
On(
    event: type[AnimationEvent],
    animation: AnimationResult | Animation,
    *,
    extend_display: bool = False,
)
```

### On.actions

Enumerate declarations for matching source events without changing the source clocks.

```python
On.actions(
    context: AnimationContext,
) -> Iterable[tuple[AnimationEvent, AnimationResult]]
```

### On.bind

Resolve the configured event declaration into Track motion and material rules.

```python
On.bind(
    context: AnimationContext,
) -> tuple[MotionRule | MaterialRule, ...]
```

### On.sample

Evaluate local seconds, independently of previously sampled frames.

Without a function or override this raises NotImplementedError.
Event-only animations use bind() instead.

```python
On.sample(
    t: float,
    context: AnimationContext,
) -> Transform
```

## OpacityTo

A seconds-based composition transition to a target opacity.

Use it with Timeline.play and a duration or TimeSpan.

[Source](../../kara_templater/choreography.py#L199)

```python
OpacityTo(
    opacity: float,
    *,
    duration: float | None = None,
    rate: RateFunction = linear,
)
```

### OpacityTo.actions

Yield typed event-bound declarations from this animation and its inherited handlers.

```python
OpacityTo.actions(
    context: AnimationContext,
) -> Iterable[tuple[AnimationEvent, AnimationResult]]
```

### OpacityTo.bind

Resolve this animation against the source context without changing the original lyric.

```python
OpacityTo.bind(
    context: AnimationContext,
) -> tuple[MotionRule | MaterialRule, ...]
```

### OpacityTo.sample

Interpolate the configured sparse geometry target at local seconds.

```python
OpacityTo.sample(
    t: float,
    context: AnimationContext,
) -> Transform
```

## Parallel

Run Track event animation declarations simultaneously.

Conflicting writes require a supported composition rule rather than implicit
ordering.

[Source](../../kara_templater/motion.py#L413)

```python
Parallel(
    *animations: AnimationResult,
)
```

## ProgressMode

Public type alias:

```python
type ProgressMode = Literal['envelope', 'singing']
```

## PropertyContext

A scalar property callback context with millisecond time/interval, progress, target metadata, display window, and seed.

Named noise is deterministic for that context.

[Source](../../kara_templater/properties.py#L27)

```python
PropertyContext(
    time_ms: float,
    progress: float,
    interval: tuple[float, float],
    window: DisplayWindow,
    target: PropertyTarget,
    seed: int,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `time_ms` | `float` | `required` |
| `progress` | `float` | `required` |
| `interval` | `tuple[float, float]` | `required` |
| `window` | `DisplayWindow` | `required` |
| `target` | `PropertyTarget` | `required` |
| `seed` | `int` | `required` |

### PropertyContext.noise

Return deterministic named noise for this target/time context and seed.

```python
PropertyContext.noise(
    channel: str = 'default',
    *,
    animated: bool = True,
    scope: Literal['target', 'source'] = 'target',
) -> float
```

## PropertyTarget

Original visual target, shared by its following decorations.

[Source](../../kara_templater/properties.py#L16)

```python
PropertyTarget(
    id: str,
    text: str,
    kind: str,
    sources: tuple[SourceRef, ...],
    source_id: str | None = None,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `id` | `str` | `required` |
| `text` | `str` | `required` |
| `kind` | `str` | `required` |
| `sources` | `tuple[SourceRef, ...]` | `required` |
| `source_id` | `str \| None` | `None` |

## PropertyValue

Public type alias:

```python
type PropertyValue = float | tuple[float, float] | Transition | Keyframes | Contextual | Callable[[float], float]
```

## RateFunction

Public type alias:

```python
type RateFunction = Callable[[float], float]
```

## ScaleTo

A seconds-based composition transition to a target uniform scale.

The enclosing Timeline determines its start and duration.

[Source](../../kara_templater/choreography.py#L183)

```python
ScaleTo(
    scale: float,
    *,
    duration: float | None = None,
    rate: RateFunction = linear,
)
```

### ScaleTo.actions

Yield typed event-bound declarations from this animation and its inherited handlers.

```python
ScaleTo.actions(
    context: AnimationContext,
) -> Iterable[tuple[AnimationEvent, AnimationResult]]
```

### ScaleTo.bind

Resolve this animation against the source context without changing the original lyric.

```python
ScaleTo.bind(
    context: AnimationContext,
) -> tuple[MotionRule | MaterialRule, ...]
```

### ScaleTo.sample

Interpolate the configured sparse geometry target at local seconds.

```python
ScaleTo.sample(
    t: float,
    context: AnimationContext,
) -> Transform
```

## SceneTimeline

Author sequential/parallel plays. Times are local to the object's birth.

[Source](../../kara_templater/scene_animation.py#L325)

```python
SceneTimeline()
```

### SceneTimeline.clips

The validated immutable AnimationClip schedule for assignment to an object.

Type: `tuple[AnimationClip, ...]`.

### SceneTimeline.keyframes

Reach successive targets at local seconds, retaining completed values.

Times must increase strictly from zero. Each frame interpolates its
declared channels from the state at the preceding frame's time; omitted
channels retain their existing animations/state. The entire insertion
is validated before changing the timeline.

```python
SceneTimeline.keyframes(
    *frames: StateKeyframe,
    at: float | None = None,
) -> SceneTimeline
```

### SceneTimeline.play

Schedule animations; breakpoints are seconds from this play's start.

All parallel animations receive these sampling boundaries. Repeating the
timeline preserves them relative to each copied clip.

```python
SceneTimeline.play(
    *animations: StateAnimation,
    duration: float,
    at: float | None = None,
    hold: bool = True,
    breakpoints: tuple[float, ...] = (),
) -> SceneTimeline
```

### SceneTimeline.repeat

Repeat a complete schedule while preserving clip-local clocks and breakpoints.

```python
SceneTimeline.repeat(
    count: int,
) -> SceneTimeline
```

### SceneTimeline.wait

Advance the local seconds cursor without scheduling an animation.

```python
SceneTimeline.wait(
    duration: float,
) -> SceneTimeline
```

## SegmentSinging

One event per source segment, including repeated readings.

[Source](../../kara_templater/motion.py#L108)

```python
SegmentSinging(
    target: AnimationTarget,
    start: Milliseconds,
    end: Milliseconds,
    index: int,
    window: DisplayWindow,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `target` | `AnimationTarget` | `required` |
| `start` | `Milliseconds` | `required` |
| `end` | `Milliseconds` | `required` |
| `index` | `int` | `required` |
| `window` | `DisplayWindow` | `required` |

## Sequence

Run Track event animation declarations consecutively. Child durations and event-

relative offsets determine the composed schedule.

[Source](../../kara_templater/motion.py#L433)

```python
Sequence(
    *animations: AnimationResult,
)
```

## SingingPulseAnimation

Apply a syllable scale envelope around singing with millisecond attack/release and configurable rise/fall rates.

Optional extension affects display, not original singing time.

[Source](../../kara_templater/motion.py#L704)

```python
SingingPulseAnimation(
    *,
    peak: float = 1.1,
    attack: Milliseconds = 80,
    release: Milliseconds = 160,
    rise: RateFunction = linear,
    fall: RateFunction = linear,
    extend_display: bool = False,
)
```

### SingingPulseAnimation.actions

Yield typed event-bound declarations from this animation and its inherited handlers.

```python
SingingPulseAnimation.actions(
    context: AnimationContext,
) -> Iterable[tuple[AnimationEvent, AnimationResult]]
```

### SingingPulseAnimation.bind

Resolve this animation against the source context without changing the original lyric.

```python
SingingPulseAnimation.bind(
    context: AnimationContext,
) -> tuple[MotionRule | MaterialRule, ...]
```

### SingingPulseAnimation.sample

Evaluate local seconds, independently of previously sampled frames.

Without a function or override this raises NotImplementedError.
Event-only animations use bind() instead.

```python
SingingPulseAnimation.sample(
    t: float,
    context: AnimationContext,
) -> Transform
```

## StateAnimation

Protocol for a pure normalized-progress state animation with explicitly declared written channels.

Implement sample without depending on prior frame evaluation.

[Source](../../kara_templater/scene_animation.py#L166)

### StateAnimation.channels

The explicit set of VisualState channels this animation may write.

Type: `frozenset[Channel]`.

### StateAnimation.sample

Evaluate normalized clip progress from the incoming state without prior-frame state.

```python
StateAnimation.sample(
    base: VisualState,
    progress: float,
) -> VisualState
```

## StateFunction

Custom pure evaluator. Declare written channels for conflict detection.

Randomness must be tied to object identity, not callback invocation order.
The compiler reports sampling intervals, not an error bound for this function.

[Source](../../kara_templater/scene_animation.py#L223)

```python
StateFunction(
    function: Callable[[VisualState, float], VisualState],
    channels: frozenset[Channel] = frozenset({'blur', 'border', 'fill', 'opacity', 'outline', 'position', 'rotation', 'scale', 'shadow', 'skew'}),
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `function` | `Callable[[VisualState, float], VisualState]` | `required` |
| `channels` | `frozenset[Channel]` | `frozenset({'blur', 'border', 'fill', 'opacity', 'outline', 'position', 'rotation', 'scale', 'shadow', 'skew'})` |

### StateFunction.sample

Call the custom normalized-progress evaluator with the incoming visual state.

```python
StateFunction.sample(
    base: VisualState,
    progress: float,
) -> VisualState
```

## StateKeyframe

A target reached at a positive local time, with an incoming easing curve.

[Source](../../kara_templater/scene_animation.py#L204)

```python
StateKeyframe(
    time: float,
    target: StatePatch,
    rate: Callable[[float], float] = linear_rate,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `time` | `float` | `required` |
| `target` | `StatePatch` | `required` |
| `rate` | `Callable[[float], float]` | `linear_rate` |

### StateKeyframe.rate

Return normalized Scene animation progress unchanged.

```python
StateKeyframe.rate(
    progress: float,
) -> float
```

## StatePatch

A sparse set of VisualState targets for interpolation.

Omitted channels retain the incoming state.

[Source](../../kara_templater/scene_animation.py#L96)

```python
StatePatch(
    *,
    position: Vec2 | None = None,
    scale: Vec2 | None = None,
    rotation: float | None = None,
    skew: Vec2 | None = None,
    opacity: float | None = None,
    fill: Color | None = None,
    outline: Color | None = None,
    border: float | None = None,
    blur: float | None = None,
    shadow: Vec2 | None = None,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `position` | `Vec2 \| None` | `None` |
| `scale` | `Vec2 \| None` | `None` |
| `rotation` | `float \| None` | `None` |
| `skew` | `Vec2 \| None` | `None` |
| `opacity` | `float \| None` | `None` |
| `fill` | `Color \| None` | `None` |
| `outline` | `Color \| None` | `None` |
| `border` | `float \| None` | `None` |
| `blur` | `float \| None` | `None` |
| `shadow` | `Vec2 \| None` | `None` |

### StatePatch.channels

The channels explicitly supplied by this sparse patch.

Type: `frozenset[Channel]`.

### StatePatch.interpolate

Interpolate supplied targets from the base state, preserving omitted channels.

```python
StatePatch.interpolate(
    base: VisualState,
    progress: float,
) -> VisualState
```

## Syllable

Namespace for a Singing event spanning the first through last segment of each timed source unit, including its internal pauses.

[Source](../../kara_templater/motion.py#L87)

```python
Syllable()
```

### Syllable.Singing

One event per timed syllable; the interval includes internal pauses.

[Source](../../kara_templater/motion.py#L90)

```python
Syllable.Singing(
    target: AnimationTarget,
    start: Milliseconds,
    end: Milliseconds,
    index: int,
    window: DisplayWindow,
)
```

#### Fields

| Name | Type | Default |
| --- | --- | --- |
| `target` | `AnimationTarget` | `required` |
| `start` | `Milliseconds` | `required` |
| `end` | `Milliseconds` | `required` |
| `index` | `int` | `required` |
| `window` | `DisplayWindow` | `required` |

## TimeInterval

Public type alias:

```python
type TimeInterval = tuple[int | TimeRef, int | TimeRef]
```

## TimeRef

A millisecond offset from a named singing/display anchor.

Adding or subtracting milliseconds creates another reference; resolve binds it
to source intervals.

[Source](../../kara_templater/properties.py#L259)

```python
TimeRef(
    anchor: str,
    offset: int = 0,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `anchor` | `str` | `required` |
| `offset` | `int` | `0` |

### TimeRef.resolve

Resolve this anchor and millisecond offset against singing segments and display window.

```python
TimeRef.resolve(
    segments: tuple[Segment, ...],
    window: DisplayWindow,
) -> int | None
```

## TimeSpan

Seconds relative to the current composition's origin.

[Source](../../kara_templater/motion.py#L143)

```python
TimeSpan(
    start: float,
    end: float,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `start` | `float` | `required` |
| `end` | `float` | `required` |

### TimeSpan.duration

The seconds difference between end and start.

Type: `float`.

### TimeSpan.interval

This seconds interval, suitable for Timeline.play(during=...).

Type: `TimeSpan`.

## Timeline

Record simultaneous plays at explicit local times, or after the cursor.

[Source](../../kara_templater/choreography.py#L40)

```python
Timeline(
    context: AnimationContext,
)
```

### Timeline.play

Schedule composed animations at local seconds or during an explicit TimeSpan.

Omitted start uses the composition cursor.

```python
Timeline.play(
    *animations: Animation,
    at: float | None = None,
    during: TimeSpan | None = None,
    duration: float | None = None,
) -> None
```

## Transform

Sparse animation output. Omitted properties are not written.

[Source](../../kara_templater/motion.py#L112)

```python
Transform(
    scale: float | None = None,
    opacity: float | None = None,
    offset_x: float | None = None,
    offset_y: float | None = None,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `scale` | `float \| None` | `None` |
| `opacity` | `float \| None` | `None` |
| `offset_x` | `float \| None` | `None` |
| `offset_y` | `float \| None` | `None` |

### Transform.values

Return only explicitly written geometry values as a typed scalar mapping.

```python
Transform.values() -> dict[str, float]
```

## TransformTo

Interpolate only the supplied properties from the state at this start.

[Source](../../kara_templater/choreography.py#L153)

```python
TransformTo(
    transform: Transform,
    *,
    duration: float | None = None,
    rate: RateFunction = linear,
)
```

### TransformTo.actions

Yield typed event-bound declarations from this animation and its inherited handlers.

```python
TransformTo.actions(
    context: AnimationContext,
) -> Iterable[tuple[AnimationEvent, AnimationResult]]
```

### TransformTo.bind

Resolve this animation against the source context without changing the original lyric.

```python
TransformTo.bind(
    context: AnimationContext,
) -> tuple[MotionRule | MaterialRule, ...]
```

### TransformTo.sample

Interpolate the configured sparse geometry target at local seconds.

```python
TransformTo.sample(
    t: float,
    context: AnimationContext,
) -> Transform
```

## Transition

A normalized scalar transition between start and end using an easing rate.

Track declarations resolve its timing independently of its values.

[Source](../../kara_templater/properties.py#L171)

```python
Transition(
    start: float,
    end: float,
    rate: Callable[[float], float] = linear,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `start` | `float` | `required` |
| `end` | `float` | `required` |
| `rate` | `Callable[[float], float]` | `linear` |

### Transition.__call__

Evaluate the eased scalar transition at normalized progress.

```python
Transition.__call__(
    progress: float,
) -> float
```

### Transition.rate

Return normalized progress unchanged for linear interpolation.

```python
Transition.rate(
    p: float,
) -> float
```

## Tween

Interpolate a StatePatch from the incoming VisualState using normalized progress and an easing rate.

The patch determines the written channels.

[Source](../../kara_templater/scene_animation.py#L182)

```python
Tween(
    target: StatePatch,
    rate: Callable[[float], float] = linear_rate,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `target` | `StatePatch` | `required` |
| `rate` | `Callable[[float], float]` | `linear_rate` |

### Tween.channels

The channels written by the target StatePatch.

Type: `frozenset[Channel]`.

### Tween.rate

Return normalized Scene animation progress unchanged.

```python
Tween.rate(
    progress: float,
) -> float
```

### Tween.sample

Interpolate the target patch using eased normalized progress.

```python
Tween.sample(
    base: VisualState,
    progress: float,
) -> VisualState
```

## VisualState

Finite drawing state in script pixels, degrees, RGB colors, and opacity 0 through 1.

Position, scale, rotation, skew, paint, blur, and shadow compose through the
scene hierarchy.

[Source](../../kara_templater/scene_animation.py#L59)

```python
VisualState(
    position: Vec2 = Vec2(x=0, y=0),
    scale: Vec2 = Vec2(x=1, y=1),
    rotation: float = 0,
    skew: Vec2 = Vec2(x=0, y=0),
    opacity: float = 1,
    fill: Color = Color(red=255, green=255, blue=255),
    outline: Color = Color(red=0, green=0, blue=0),
    border: float = 0,
    blur: float = 0,
    shadow: Vec2 = Vec2(x=0, y=0),
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `position` | `Vec2` | `Vec2(x=0, y=0)` |
| `scale` | `Vec2` | `Vec2(x=1, y=1)` |
| `rotation` | `float` | `0` |
| `skew` | `Vec2` | `Vec2(x=0, y=0)` |
| `opacity` | `float` | `1` |
| `fill` | `Color` | `Color(red=255, green=255, blue=255)` |
| `outline` | `Color` | `Color(red=0, green=0, blue=0)` |
| `border` | `float` | `0` |
| `blur` | `float` | `0` |
| `shadow` | `Vec2` | `Vec2(x=0, y=0)` |

### VisualState.singular

Whether this linear map collapses filled geometry to zero area.

Type: `bool`.

### VisualState.transform

Local shear, axis scale, clockwise rotation, then translation.

Type: `Affine2D`.

## display

Public constant:

```python
display = _Clock(start=TimeRef(anchor='display.start', offset=0), end=TimeRef(anchor='display.end', offset=0))
```

## ease_in

An accelerating scalar easing curve for normalized progress.

[Source](../../kara_templater/properties.py#L89)

```python
ease_in(
    p: float,
) -> float
```

## ease_in_out

A scalar easing curve that accelerates then decelerates across normalized progress.

[Source](../../kara_templater/properties.py#L99)

```python
ease_in_out(
    p: float,
) -> float
```

## ease_out

A decelerating scalar easing curve for normalized progress.

[Source](../../kara_templater/properties.py#L94)

```python
ease_out(
    p: float,
) -> float
```

## linear

Return normalized progress unchanged for linear interpolation.

[Source](../../kara_templater/properties.py#L79)

```python
linear(
    p: float,
) -> float
```

## linear_rate

Return normalized Scene animation progress unchanged.

[Source](../../kara_templater/scene_animation.py#L49)

```python
linear_rate(
    progress: float,
) -> float
```

## on

Declare a typed event handler on an Animation subclass.

The handler receives the requested event type and returns supported animation
declarations.

[Source](../../kara_templater/motion.py#L508)

```python
on(
    event_type: type[E],
    *,
    where: SourceMatch | None = None,
) -> _EventDecorator[E]
```

## singing

Public constant:

```python
singing = _Clock(start=TimeRef(anchor='singing.start', offset=0), end=TimeRef(anchor='singing.end', offset=0))
```

## smooth

Smoothly ease normalized progress with flat endpoints.

[Source](../../kara_templater/properties.py#L84)

```python
smooth(
    p: float,
) -> float
```

## smooth_rate

Ease Scene animation progress smoothly between endpoints.

[Source](../../kara_templater/scene_animation.py#L54)

```python
smooth_rate(
    progress: float,
) -> float
```

## there_and_back

Use as a rate directly, or configure a peak, hold, rise and fall.

[Source](../../kara_templater/properties.py#L126)

```python
there_and_back(
    p: float,
    *,
    peak_at: float = 0.5,
    return_at: float | None = None,
    rise: Callable[[float], float] = linear,
    fall: Callable[[float], float] = linear,
) -> float
```

```python
there_and_back(
    p: None = None,
    *,
    peak_at: float = 0.5,
    return_at: float | None = None,
    rise: Callable[[float], float] = linear,
    fall: Callable[[float], float] = linear,
) -> BackRate
```
