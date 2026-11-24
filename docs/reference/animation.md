# Animation and timing

Pure state/property animation and typed composition. Scene, semantic lyric rules, and animation sequences use seconds. See the [time-unit table](../guides/animation.md).

[All public symbols](README.md#symbol-index)

## Contents

- [Animation](#animation)
- [AnimationClip](#animationclip)
- [AnimationSequence](#animationsequence)
- [BackRate](#backrate)
- [Canvas](#canvas)
- [Channel](#channel)
- [CurveIn](#curvein)
- [DriftOut](#driftout)
- [FadeIn](#fadein)
- [FadeOut](#fadeout)
- [Glyph](#glyph)
- [Jump](#jump)
- [LengthExpr](#lengthexpr)
- [Note](#note)
- [ScalePulse](#scalepulse)
- [ShaderMotion](#shadermotion)
- [Slide](#slide)
- [StateAnimation](#stateanimation)
- [StateFunction](#statefunction)
- [StateKeyframe](#statekeyframe)
- [StatePatch](#statepatch)
- [TimeExpr](#timeexpr)
- [TimeSpan](#timespan)
- [Timeline](#timeline)
- [Transform](#transform)
- [Tween](#tween)
- [VisualState](#visualstate)
- [ease_in](#ease_in)
- [ease_in_out](#ease_in_out)
- [ease_out](#ease_out)
- [linear_rate](#linear_rate)
- [smooth_rate](#smooth_rate)
- [smoother_rate](#smoother_rate)
- [there_and_back](#there_and_back)

## Animation

Animation.duration reads the requested animation duration or its bound interval.

[Source](../../kara_templater/parameters.py#L111)

```python
Animation()
```

## AnimationClip

A positive-duration state animation starting at local clock seconds.

hold retains final written channels; breakpoints are offsets from the clip
start. Negative starts support visibility extended before a preserved clock
origin. The owning node validates that the absolute start is nonnegative;
nested sequences and Timeline still start at zero or later.

[Source](../../kara_templater/scene_animation.py#L632)

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

## AnimationSequence

A nested schedule evaluated by the same clip evaluator as a visual node.

Build through Timeline.animation. Duration is the schedule's local length;
normalized outer progress maps onto that length. There is no secondary
evaluator or incremental playback state.

[Source](../../kara_templater/scene_animation.py#L849)

```python
AnimationSequence(
    clips: tuple[AnimationClip, ...],
    duration: float,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `clips` | `tuple[AnimationClip, ...]` | `required` |
| `duration` | `float` | `required` |

### AnimationSequence.breakpoints

Normalized internal boundaries, including nested child boundaries.

Type: `tuple[float, ...]`.

### AnimationSequence.channels

All channels written by the schedule.

Type: `frozenset[Channel]`.

### AnimationSequence.sample

Evaluate the immutable schedule at normalized outer progress.

```python
AnimationSequence.sample(
    base: VisualState,
    progress: float,
) -> VisualState
```

## BackRate

Piecewise rise, hold and fall on normalized progress, independent of clocks.

[Source](../../kara_templater/easing.py#L71)

```python
BackRate(
    peak_at: float,
    return_at: float,
    rise: Callable[[float], float],
    fall: Callable[[float], float],
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `peak_at` | `float` | `required` |
| `return_at` | `float` | `required` |
| `rise` | `Callable[[float], float]` | `required` |
| `fall` | `Callable[[float], float]` | `required` |

### BackRate.__call__

Evaluate the configured rise, hold or fall without advancing state.

```python
BackRate.__call__(
    progress: float,
) -> float
```

## Canvas

Canvas.height reads the document's vertical script resolution.

[Source](../../kara_templater/parameters.py#L99)

```python
Canvas()
```

## Channel

Public type alias:

```python
type Channel = Literal['position', 'scale', 'rotation', 'skew', 'opacity', 'fill', 'outline', 'border', 'blur', 'shadow']
```

## CurveIn

Reveal text along a quadratic local-offset trajectory to its base pose.

offset is the initial parent-space displacement and bend is the quadratic
control offset; the final offset is zero. scale and rotation are the initial
relative scale factor and added degrees. rate eases trajectory, pose and
opacity together. Omitted pivot follows LyricRule's measured-center policy.

[Source](../../kara_templater/scene_animation.py#L527)

```python
CurveIn(
    offset: Vec2 = Vec2(x=-40, y=24),
    bend: Vec2 = Vec2(x=20, y=-36),
    scale: float = 0.85,
    rotation: float = -12,
    pivot: Vec2 | None = None,
    rate: Callable[[float], float] = smooth_rate,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `offset` | `Vec2` | `Vec2(x=-40, y=24)` |
| `bend` | `Vec2` | `Vec2(x=20, y=-36)` |
| `scale` | `float` | `0.85` |
| `rotation` | `float` | `-12` |
| `pivot` | `Vec2 \| None` | `None` |
| `rate` | `Callable[[float], float]` | `smooth_rate` |

### CurveIn.channels

Relative position, scale, rotation and opacity.

Type: `frozenset[Channel]`.

### CurveIn.sample

Use the common relative transform to follow the authored curve.

```python
CurveIn.sample(
    base: VisualState,
    progress: float,
) -> VisualState
```

## DriftOut

Drift away while shrinking and fading, using the common relative transform.

offset is the total displacement in parent-space script pixels. scale is the
final factor on captured scale; pivot is local. rate controls travel, shrink
and fade over normalized progress. travel_rate overrides only displacement
easing (None follows rate); linear_rate gives constant-speed travel. Duration and any pause belong to binding.
An omitted pivot uses the local origin on direct objects and the measured
target center when bound with LyricRule. Vec2() explicitly selects the origin.

[Source](../../kara_templater/scene_animation.py#L486)

```python
DriftOut(
    offset: Vec2 = Vec2(x=0, y=-36),
    scale: float = 0.96,
    pivot: Vec2 | None = None,
    rate: Callable[[float], float] = smooth_rate,
    travel_rate: Callable[[float], float] | None = None,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `offset` | `Vec2` | `Vec2(x=0, y=-36)` |
| `scale` | `float` | `0.96` |
| `pivot` | `Vec2 \| None` | `None` |
| `rate` | `Callable[[float], float]` | `smooth_rate` |
| `travel_rate` | `Callable[[float], float] \| None` | `None` |

### DriftOut.channels

Travel/pivot, relative scale and captured opacity.

Type: `frozenset[Channel]`.

### DriftOut.sample

Apply the same transform an author can express with custom callbacks.

```python
DriftOut.sample(
    base: VisualState,
    progress: float,
) -> VisualState
```

## FadeIn

Reveal the incoming opacity from zero, using normalized progress.

The final opacity is the captured base opacity, including any prior held
animation. This works identically on a drawing or a visual parent.

[Source](../../kara_templater/scene_animation.py#L376)

```python
FadeIn(
    rate: Callable[[float], float] = linear_rate,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `rate` | `Callable[[float], float]` | `linear_rate` |

### FadeIn.channels

Only opacity is written.

Type: `frozenset[Channel]`.

### FadeIn.sample

Reveal the captured opacity without changing other channels.

```python
FadeIn.sample(
    base: VisualState,
    progress: float,
) -> VisualState
```

## FadeOut

Reduce the incoming opacity to zero, using normalized progress.

[Source](../../kara_templater/scene_animation.py#L396)

```python
FadeOut(
    rate: Callable[[float], float] = linear_rate,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `rate` | `Callable[[float], float]` | `linear_rate` |

### FadeOut.channels

Only opacity is written.

Type: `frozenset[Channel]`.

### FadeOut.sample

Fade the captured opacity without changing other channels.

```python
FadeOut.sample(
    base: VisualState,
    progress: float,
) -> VisualState
```

## Glyph

Glyph.font_size reads the current body or reading's authored font size.

[Source](../../kara_templater/parameters.py#L93)

```python
Glyph()
```

## Jump

Move up and return to the captured position over normalized progress.

Height is in script pixels; a negative height moves downward. Durations and
lyric singing anchors belong to clip binding, not to this animation.

[Source](../../kara_templater/scene_animation.py#L412)

```python
Jump(
    height: float = 12,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `height` | `float` | `12` |

### Jump.channels

Only position is written.

Type: `frozenset[Channel]`.

### Jump.sample

Return the captured position exactly at both endpoints.

```python
Jump.sample(
    base: VisualState,
    progress: float,
) -> VisualState
```

## LengthExpr

A script-pixel length measured from a glyph or canvas at preparation.

[Source](../../kara_templater/parameters.py#L71)

```python
LengthExpr()
```

### LengthExpr.clamp

Limit the resolved value to inclusive bounds in the parameter's units.

```python
LengthExpr.clamp(
    minimum: float,
    maximum: float,
) -> Self
```

## Note

Note.duration reads the source singing interval, including each repeat.

[Source](../../kara_templater/parameters.py#L105)

```python
Note()
```

## ScalePulse

Scale up and back around a fixed local pivot over normalized progress.

peak multiplies the captured scale; values between zero and one shrink.
peak_at locates the peak within normalized progress (strictly between 0 and 1).
rate eases each attack/release phase; the default has zero endpoint velocity.
Position is adjusted to preserve
the pivot under existing scale, rotation and skew. Binding chooses duration
and lyric anchors; this animation works on ordinary objects and groups too.
An omitted pivot uses the local origin on direct objects and the measured
target center when bound with LyricRule. Vec2() explicitly selects the origin.

[Source](../../kara_templater/scene_animation.py#L436)

```python
ScalePulse(
    pivot: Vec2 | None = None,
    peak: float = 1.1,
    peak_at: float = 0.5,
    rate: Callable[[float], float] = smooth_rate,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `pivot` | `Vec2 \| None` | `None` |
| `peak` | `float` | `1.1` |
| `peak_at` | `float` | `0.5` |
| `rate` | `Callable[[float], float]` | `smooth_rate` |

### ScalePulse.channels

Scale and pivot compensation both participate in conflict detection.

Type: `frozenset[Channel]`.

### ScalePulse.sample

Return the captured state at endpoints and preserve all other channels.

```python
ScalePulse.sample(
    base: VisualState,
    progress: float,
) -> VisualState
```

## ShaderMotion

Affine GPU animation with a seekable Python evaluator for state capture.

The GLSL body receives normalized progress p, parameters at data via item(),
and mutable local channels pos, scale, skew, angle (degrees), alpha, pen
(outline radius), fill and outline (RGB in 0..1).
basisOf(scale, skew, angle) returns the local linear transform.
Supply the same motion in function for evaluation at authored boundaries.

[Source](../../kara_templater/scene_animation.py#L603)

```python
ShaderMotion(
    function: Callable[[VisualState, float], VisualState],
    channels: frozenset[Channel] = frozenset({'blur', 'border', 'fill', 'opacity', 'outline', 'position', 'rotation', 'scale', 'shadow', 'skew'}),
    source: str = '',
    parameters: tuple[float, ...] = (),
    progress_scale: float = 1.0,
    progress_offset: float = 0.0,
    functions: str = '',
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `function` | `Callable[[VisualState, float], VisualState]` | `required` |
| `channels` | `frozenset[Channel]` | `frozenset({'blur', 'border', 'fill', 'opacity', 'outline', 'position', 'rotation', 'scale', 'shadow', 'skew'})` |
| `source` | `str` | `''` |
| `parameters` | `tuple[float, ...]` | `()` |
| `progress_scale` | `float` | `1.0` |
| `progress_offset` | `float` | `0.0` |
| `functions` | `str` | `''` |

### ShaderMotion.sample

Evaluate the same local motion at a scene clock boundary.

```python
ShaderMotion.sample(
    base: VisualState,
    progress: float,
) -> VisualState
```

## Slide

Translate by a relative offset in script pixels and fade over the bound interval.

An entrance moves from offset to rest. By default it reaches full opacity
in the first quarter. Set fast_reveal=False to fade along the travel curve.
An exit moves from rest to offset and fades throughout. Hook playback
interpolates eligible intervals directly from the offset and easing.

[Source](../../kara_templater/scene_animation.py#L340)

```python
Slide(
    offset: Vec2,
    entering: bool,
    fast_reveal: bool = True,
    rate: Callable[[float], float] = smooth_rate,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `offset` | `Vec2` | `required` |
| `entering` | `bool` | `required` |
| `fast_reveal` | `bool` | `True` |
| `rate` | `Callable[[float], float]` | `smooth_rate` |

### Slide.channels

Move and fade relative to the captured state.

Type: `frozenset[Channel]`.

### Slide.sample

Evaluate the pose at normalized progress.

```python
Slide.sample(
    base: VisualState,
    progress: float,
) -> VisualState
```

## StateAnimation

Protocol for a pure normalized-progress state animation with explicitly declared written channels.

Implement sample without depending on prior frame evaluation.

[Source](../../kara_templater/scene_animation.py#L218)

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
Standalone outputs require a compilable animation declaration.

[Source](../../kara_templater/scene_animation.py#L584)

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

[Source](../../kara_templater/scene_animation.py#L565)

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

## StatePatch

A sparse set of VisualState targets for interpolation.

Omitted channels retain the incoming state.

[Source](../../kara_templater/scene_animation.py#L147)

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

## TimeExpr

Seconds measured from a singing interval or its bound animation.

[Source](../../kara_templater/parameters.py#L82)

```python
TimeExpr()
```

### TimeExpr.clamp

Limit the resolved value to inclusive bounds in the parameter's units.

```python
TimeExpr.clamp(
    minimum: float,
    maximum: float,
) -> Self
```

## TimeSpan

A finite seconds interval, including zero-length singing spans.

The binding context determines whether its endpoints are absolute or local.

[Source](../../kara_templater/scene_animation.py#L70)

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

Author sequential/parallel plays. Times are local to the object's birth.

[Source](../../kara_templater/scene_animation.py#L748)

```python
Timeline()
```

### Timeline.animation

Freeze this schedule as an animation reusable on any visual target.

The containing clip's duration scales the entire schedule, including
waits and repeats. Interior boundaries propagate into ordinary sampling.

Type: `AnimationSequence`.

### Timeline.clips

The validated immutable AnimationClip schedule for assignment to an object.

Type: `tuple[AnimationClip, ...]`.

### Timeline.keyframes

Reach successive targets at local seconds, retaining completed values.

Times must increase strictly from zero. Each frame interpolates its
declared channels from the state at the preceding frame's time; omitted
channels retain their existing animations/state. The entire insertion
is validated before changing the timeline.

```python
Timeline.keyframes(
    *frames: StateKeyframe,
    at: float | None = None,
) -> Timeline
```

### Timeline.play

Schedule animations; breakpoints are seconds from this play's start.

All parallel animations receive these sampling boundaries. Repeating the
timeline preserves them relative to each copied clip.

```python
Timeline.play(
    *animations: StateAnimation,
    duration: float,
    at: float | None = None,
    hold: bool = True,
    breakpoints: tuple[float, ...] = (),
) -> Timeline
```

### Timeline.repeat

Repeat a complete schedule while preserving clip-local clocks and breakpoints.

```python
Timeline.repeat(
    count: int,
) -> Timeline
```

### Timeline.wait

Advance the local seconds cursor without scheduling an animation.

```python
Timeline.wait(
    duration: float,
) -> Timeline
```

## Transform

Custom relative motion from normalized progress, with inferred channels.

Each supplied value is constant or a pure function of progress in 0..1.
offset adds parent-space script pixels; scale multiplies captured scale
(a scalar applies to both axes); rotation adds degrees; opacity multiplies
captured opacity. Omitted fields do not write their channels. Constant values
apply throughout the clip, rather than interpolating toward that value.

Scaling/rotation preserve the local pivot's transformed position before
applying offset. Both therefore also write position. StateFunction remains
available for custom behavior needing the complete incoming VisualState.
An omitted pivot uses the local origin on direct objects; LyricRule resolves
it to the measured target center. Pass Vec2() to explicitly keep the origin.

[Source](../../kara_templater/scene_animation.py#L235)

```python
Transform(
    *,
    offset: Vec2 | Callable[[float], Vec2] | None = None,
    scale: float | Vec2 | Callable[[float], float | Vec2] | None = None,
    rotation: float | Callable[[float], float] | None = None,
    opacity: float | Callable[[float], float] | None = None,
    pivot: Vec2 | None = None,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `offset` | `Vec2 \| Callable[[float], Vec2] \| None` | `None` |
| `scale` | `float \| Vec2 \| Callable[[float], float \| Vec2] \| None` | `None` |
| `rotation` | `float \| Callable[[float], float] \| None` | `None` |
| `opacity` | `float \| Callable[[float], float] \| None` | `None` |
| `pivot` | `Vec2 \| None` | `None` |

### Transform.channels

Infer writes from supplied fields, including pivot compensation.

Type: `frozenset[Channel]`.

### Transform.sample

Apply relative values to the captured state, independently of seek order.

```python
Transform.sample(
    base: VisualState,
    progress: float,
) -> VisualState
```

## Tween

Interpolate a StatePatch from the incoming VisualState using normalized progress and an easing rate.

The patch determines the written channels.

[Source](../../kara_templater/scene_animation.py#L318)

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
shadow_opacity multiplies the drawing opacity for the shadow alone.

[Source](../../kara_templater/scene_animation.py#L96)

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
    shadow_opacity: float = 1,
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
| `shadow_opacity` | `float` | `1` |

### VisualState.singular

Whether this linear map collapses filled geometry to zero area.

Type: `bool`.

### VisualState.transform

Local shear, axis scale, clockwise rotation, then translation.

Type: `Affine2D`.

## ease_in

An accelerating scalar easing curve for normalized progress.

[Source](../../kara_templater/easing.py#L13)

```python
ease_in(
    p: float,
) -> float
```

## ease_in_out

A scalar easing curve that accelerates then decelerates across normalized progress.

[Source](../../kara_templater/easing.py#L23)

```python
ease_in_out(
    p: float,
) -> float
```

## ease_out

A decelerating scalar easing curve for normalized progress.

[Source](../../kara_templater/easing.py#L18)

```python
ease_out(
    p: float,
) -> float
```

## linear_rate

Return normalized Scene animation progress unchanged.

[Source](../../kara_templater/scene_animation.py#L51)

```python
linear_rate(
    progress: float,
) -> float
```

## smooth_rate

Ease Scene animation progress smoothly between endpoints.

[Source](../../kara_templater/scene_animation.py#L56)

```python
smooth_rate(
    progress: float,
) -> float
```

## smoother_rate

Quintic easing with zero velocity and acceleration at both endpoints.

Input is normalized progress in [0, 1]; outside that interval the polynomial
extrapolates. Use as a rate for shared animations or inside custom curves.

[Source](../../kara_templater/scene_animation.py#L61)

```python
smoother_rate(
    progress: float,
) -> float
```

## there_and_back

Use as a rate directly, or configure a peak, hold, rise and fall.

[Source](../../kara_templater/easing.py#L50)

```python
there_and_back(
    p: float,
    *,
    peak_at: float = 0.5,
    return_at: float | None = None,
    rise: Callable[[float], float] = linear_rate,
    fall: Callable[[float], float] = linear_rate,
) -> float
```

```python
there_and_back(
    p: None = None,
    *,
    peak_at: float = 0.5,
    return_at: float | None = None,
    rise: Callable[[float], float] = linear_rate,
    fall: Callable[[float], float] = linear_rate,
) -> BackRate
```
