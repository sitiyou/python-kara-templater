# Native layers and singing timelines

Low-level typed building blocks for native ASS layers, highlight timing, and sampling. Clocks use milliseconds unless a description says otherwise. Compose lowered events into Scene with NativeEvent.

[All public symbols](README.md#symbol-index)

## Contents

- [AnimationPlan](#animationplan)
- [CharacterTarget](#charactertarget)
- [ClipSpan](#clipspan)
- [CompiledLayers](#compiledlayers)
- [DisplayWindow](#displaywindow)
- [DynamicEffect](#dynamiceffect)
- [DynamicProperties](#dynamicproperties)
- [EdgeSweep](#edgesweep)
- [Fade](#fade)
- [Follow](#follow)
- [HighlightEnter](#highlightenter)
- [HighlightTrack](#highlighttrack)
- [OffsetAnimation](#offsetanimation)
- [OpacityAnimation](#opacityanimation)
- [OutputCapabilityError](#outputcapabilityerror)
- [OutputSettings](#outputsettings)
- [ProgressCurve](#progresscurve)
- [Pulse](#pulse)
- [Region](#region)
- [SampleContext](#samplecontext)
- [SamplingEstimate](#samplingestimate)
- [SamplingPlan](#samplingplan)
- [SamplingSettings](#samplingsettings)
- [ScaleAnimation](#scaleanimation)
- [SegmentStart](#segmentstart)
- [SingingPass](#singingpass)
- [SyllableStart](#syllablestart)
- [TextLayer](#textlayer)
- [compile_layers](#compile_layers)
- [plan_pulses](#plan_pulses)
- [prepare_sampling](#prepare_sampling)
- [sweep_spans](#sweep_spans)
- [tracks_from_layout](#tracks_from_layout)
- [union_regions](#union_regions)

## AnimationPlan

Resolved scale animations, their display window, and scheduling diagnostics.

This low-level plan retains source target IDs rather than generated ASS layers.

[Source](../../kara_templater/animation.py#L240)

```python
AnimationPlan(
    animations: tuple[ScaleAnimation, ...],
    window: DisplayWindow,
    diagnostics: tuple[str, ...] = (),
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `animations` | `tuple[ScaleAnimation, ...]` | `required` |
| `window` | `DisplayWindow` | `required` |
| `diagnostics` | `tuple[str, ...]` | `()` |

## CharacterTarget

An independently drawable cluster supplied by layout, never a codepoint.

A layout backend must establish that the cluster can be drawn independently.
This model deliberately does not split text or claim shaping support.

[Source](../../kara_templater/animation.py#L12)

```python
CharacterTarget(
    id: str,
    unit_index: int,
    region: Region,
    center_y: float,
    drawable: bool = True,
    center_x: float | None = None,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `id` | `str` | `required` |
| `unit_index` | `int` | `required` |
| `region` | `Region` | `required` |
| `center_y` | `float` | `required` |
| `drawable` | `bool` | `True` |
| `center_x` | `float \| None` | `None` |

## ClipSpan

A linear rectangular mask over a half-open absolute time interval.

Separate spans allow instantaneous resets without ambiguous duplicate keys.
Coordinates are in the original text layout and follow scale transforms.

[Source](../../kara_templater/ass_output.py#L112)

```python
ClipSpan(
    start_ms: float,
    end_ms: float,
    start: Region,
    end: Region,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `start_ms` | `float` | `required` |
| `end_ms` | `float` | `required` |
| `start` | `Region` | `required` |
| `end` | `Region` | `required` |

### ClipSpan.at

Interpolate clip boundaries at the requested millisecond time using the span clock.

```python
ClipSpan.at(
    time_ms: float,
) -> Region
```

## CompiledLayers

Native ASS events, diagnostics, and an aligned optional source origin for each event.

The result does not insert events into a Document.

[Source](../../kara_templater/ass_output.py#L300)

```python
CompiledLayers(
    events: tuple[Line, ...],
    diagnostics: tuple[str, ...],
    origins: tuple[EventOrigin | None, ...] = (),
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `events` | `tuple[Line, ...]` | `required` |
| `diagnostics` | `tuple[str, ...]` | `required` |
| `origins` | `tuple[EventOrigin \| None, ...]` | `()` |

## DisplayWindow

An absolute millisecond visibility interval independent of source singing time.

Animation padding changes this window rather than lyric segment clocks.

[Source](../../kara_templater/timeline.py#L31)

```python
DisplayWindow(
    start_ms: int,
    end_ms: int,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `start_ms` | `int` | `required` |
| `end_ms` | `int` | `required` |

## DynamicEffect

A low-level pure SampleContext callback returning DynamicProperties with sampling, seed, blur bounds, and absolute millisecond breakpoints.

Evaluation is separate from preparation.

[Source](../../kara_templater/sampling.py#L109)

```python
DynamicEffect(
    function: Callable[[SampleContext], DynamicProperties],
    sampling: SamplingSettings = SamplingSettings(step_ms=40, max_samples=100000),
    seed: int = 0,
    max_glow_blur: float | None = None,
    breakpoints: tuple[float, ...] = (),
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `function` | `Callable[[SampleContext], DynamicProperties]` | `required` |
| `sampling` | `SamplingSettings` | `SamplingSettings(step_ms=40, max_samples=100000)` |
| `seed` | `int` | `0` |
| `max_glow_blur` | `float \| None` | `None` |
| `breakpoints` | `tuple[float, ...]` | `()` |

## DynamicProperties

Resolved low-level geometry and material values for one sampled target.

Optional fields preserve the underlying paint when not supplied.

[Source](../../kara_templater/sampling.py#L41)

```python
DynamicProperties(
    offset_x: float = 0,
    offset_y: float = 0,
    opacity: float = 1,
    glow_blur: float | None = None,
    glow_opacity: float | None = None,
    scale: float = 1,
    pivot: tuple[float, float] | None = None,
    fill: Color | None = None,
    stroke: Color | None = None,
    stroke_width: float | None = None,
    glow_color: Color | None = None,
    glow_width: float | None = None,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `offset_x` | `float` | `0` |
| `offset_y` | `float` | `0` |
| `opacity` | `float` | `1` |
| `glow_blur` | `float \| None` | `None` |
| `glow_opacity` | `float \| None` | `None` |
| `scale` | `float` | `1` |
| `pivot` | `tuple[float, float] \| None` | `None` |
| `fill` | `Color \| None` | `None` |
| `stroke` | `Color \| None` | `None` |
| `stroke_width` | `float \| None` | `None` |
| `glow_color` | `Color \| None` | `None` |
| `glow_width` | `float \| None` | `None` |

## EdgeSweep

Low-level spatial padding and millisecond lead/tail compensation around a singing front.

It preserves the cursor on the original body domain.

[Source](../../kara_templater/timeline.py#L172)

```python
EdgeSweep(
    padding_px: float = 0,
    lead_ms: int = 0,
    tail_ms: int = 0,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `padding_px` | `float` | `0` |
| `lead_ms` | `int` | `0` |
| `tail_ms` | `int` | `0` |

### EdgeSweep.position_at

Decorative front only; never feed this result into singing triggers.

The paint extent may be re-evaluated for dynamic effects each frame.
It must enclose the timing region. Padding expands that safe extent.

```python
EdgeSweep.position_at(
    singing: SingingPass,
    paint: Region,
    time_ms: float,
) -> float
```

## Fade

Native fade-in and fade-out durations in milliseconds.

Opacity evaluation is relative to the selected display window.

[Source](../../kara_templater/ass_output.py#L81)

```python
Fade(
    in_ms: int = 0,
    out_ms: int = 0,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `in_ms` | `int` | `0` |
| `out_ms` | `int` | `0` |

### Fade.opacity_at

Evaluate combined fade opacity at a millisecond time within the display window.

```python
Fade.opacity_at(
    time_ms: float,
    window: DisplayWindow,
) -> float
```

## Follow

Choose which body motion properties a reading or decoration follows.

Position, scale, opacity, and fade are independent switches.

[Source](../../kara_templater/follow.py#L6)

```python
Follow(
    position: bool = True,
    scale: bool = True,
    opacity: bool = True,
    fade: bool = True,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `position` | `bool` | `True` |
| `scale` | `bool` | `True` |
| `opacity` | `bool` | `True` |
| `fade` | `bool` | `True` |

### Follow.allows

Whether this following policy enables the requested motion property.

```python
Follow.allows(
    property: str,
) -> bool
```

## HighlightEnter

Trigger a character animation when a highlight front reaches its enter, center, or complete threshold.

Thresholds are measured on the drawable character region.

[Source](../../kara_templater/animation.py#L37)

```python
HighlightEnter(
    threshold: str = 'enter',
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `threshold` | `str` | `'enter'` |

## HighlightTrack

A named sequence of singing passes for one source unit with explicit completion behavior.

Regions are evaluated in script pixels at millisecond time.

[Source](../../kara_templater/timeline.py#L227)

```python
HighlightTrack(
    id: str,
    unit_index: int,
    passes: tuple[SingingPass, ...],
    repeat: str = 'hold',
    end_behavior: str = 'hold',
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `id` | `str` | `required` |
| `unit_index` | `int` | `required` |
| `passes` | `tuple[SingingPass, ...]` | `required` |
| `repeat` | `str` | `'hold'` |
| `end_behavior` | `str` | `'hold'` |

### HighlightTrack.regions_at

Return the active highlighted horizontal regions at a millisecond time, including completion policy.

```python
HighlightTrack.regions_at(
    time_ms: float,
) -> tuple[Region, ...]
```

## OffsetAnimation

Known piecewise-linear translation applied after scaling.

[Source](../../kara_templater/animation.py#L135)

```python
OffsetAnimation(
    points: tuple[tuple[float, float], ...],
    axis: str,
    keep: bool = False,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `points` | `tuple[tuple[float, float], ...]` | `required` |
| `axis` | `str` | `required` |
| `keep` | `bool` | `False` |

## OpacityAnimation

Known piecewise-linear opacity; group multiplies, glow replaces glow alpha.

[Source](../../kara_templater/animation.py#L163)

```python
OpacityAnimation(
    points: tuple[tuple[float, float], ...],
    keep: bool = False,
    component: str = 'group',
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `points` | `tuple[tuple[float, float], ...]` | `required` |
| `keep` | `bool` | `False` |
| `component` | `str` | `'group'` |

## OutputCapabilityError

An output failure with optional source and absolute-time context.

[Source](../../kara_templater/ass_output.py#L25)

```python
OutputCapabilityError(
    message: str,
    *,
    origin: EventOrigin | None = None,
    time_ms: float | None = None,
)
```

## OutputSettings

Native layer/preparation limits and script resolution.

clip_error_px bounds supported curve subdivision; optional raster settings
select explicit material encoding. Final Scene budgets apply separately.

[Source](../../kara_templater/ass_output.py#L273)

```python
OutputSettings(
    resolution: tuple[int, int] = (1920, 1080),
    max_events: int = 10000,
    clip_error_px: float = 0.25,
    raster: RasterSettings | None = None,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `resolution` | `tuple[int, int]` | `(1920, 1080)` |
| `max_events` | `int` | `10000` |
| `clip_error_px` | `float` | `0.25` |
| `raster` | `RasterSettings \| None` | `None` |

## ProgressCurve

Monotone piecewise linear (normalized time, progress) knots.

Repeated progress values represent pauses. Repeated times are forbidden;
instantaneous singing is represented by a zero-duration SingingPass.

[Source](../../kara_templater/timeline.py#L76)

```python
ProgressCurve(
    knots: tuple[tuple[float, float], ...] = ((0, 0), (1, 1)),
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `knots` | `tuple[tuple[float, float], ...]` | `((0, 0), (1, 1))` |

### ProgressCurve.arrival

Earliest normalized time reaching progress, including plateau starts.

```python
ProgressCurve.arrival(
    progress: float,
) -> float
```

### ProgressCurve.at

Evaluate normalized sweep progress from this piecewise-linear curve.

```python
ProgressCurve.at(
    time_fraction: float,
) -> float
```

### ProgressCurve.two_stage

Construct a piecewise-linear progress curve through one explicit time/progress breakpoint.

```python
ProgressCurve.two_stage(
    *,
    time_fraction: float,
    progress_fraction: float,
) -> Self
```

## Pulse

Declare a highlight or singing-start scale trigger with target, pivot, duration, and retrigger policy.

Fixed durations use milliseconds; traversal duration follows the selected
singing pass.

[Source](../../kara_templater/animation.py#L75)

```python
Pulse(
    trigger: HighlightEnter | SyllableStart | SegmentStart = HighlightEnter(threshold='enter'),
    target: str = 'triggering_char',
    pivot: str = 'char_center',
    scale: float = 1.1,
    duration_ms: int | Literal['traversal'] = 'traversal',
    tracks: str = 'first',
    track_id: str | None = None,
    retrigger: bool = True,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `trigger` | `HighlightEnter \| SyllableStart \| SegmentStart` | `HighlightEnter(threshold='enter')` |
| `target` | `str` | `'triggering_char'` |
| `pivot` | `str` | `'char_center'` |
| `scale` | `float` | `1.1` |
| `duration_ms` | `int \| Literal['traversal']` | `'traversal'` |
| `tracks` | `str` | `'first'` |
| `track_id` | `str \| None` | `None` |
| `retrigger` | `bool` | `True` |

### Pulse.each_char

Create a pulse triggered by each drawable character threshold crossing.

```python
Pulse.each_char(
    **kwargs: Unpack[PulseOptions],
) -> Self
```

### Pulse.simultaneous_chars

Create separate character-center pulses triggered together at a syllable start.

```python
Pulse.simultaneous_chars(
    **kwargs: Unpack[PulseTiming],
) -> Self
```

### Pulse.whole_syllable

Create a shared syllable-center pulse at a syllable start for low-level scheduling.

```python
Pulse.whole_syllable(
    **kwargs: Unpack[PulseTiming],
) -> Self
```

## Region

A horizontal interval in script pixels; an empty interval is valid.

[Source](../../kara_templater/timeline.py#L48)

```python
Region(
    left: float,
    right: float,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `left` | `float` | `required` |
| `right` | `float` | `required` |

### Region.at

Interpolate a position across the region using normalized progress.

```python
Region.at(
    progress: float,
) -> float
```

### Region.center

The midpoint of the horizontal region.

Type: `float`.

### Region.width

The horizontal region extent in script pixels.

Type: `float`.

## SampleContext

A native Track sampling context with millisecond time, normalized progress, target ID, window, and deterministic seed.

Named noise does not depend on call order.

[Source](../../kara_templater/sampling.py#L16)

```python
SampleContext(
    time_ms: float,
    progress: float,
    window: DisplayWindow,
    target_id: str,
    seed: int,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `time_ms` | `float` | `required` |
| `progress` | `float` | `required` |
| `window` | `DisplayWindow` | `required` |
| `target_id` | `str` | `required` |
| `seed` | `int` | `required` |

### SampleContext.noise

Stable [0, 1) noise, shared by all visual layers of a target.

No mutable RNG or Python process-dependent hash is involved. Set
animated=False to obtain a stable per-target phase or amplitude.

```python
SampleContext.noise(
    channel: str = 'default',
    *,
    animated: bool = True,
) -> float
```

## SamplingEstimate

Conservative target-sample and event counts before evaluation/merging at step_ms.

Native subdivision and final encoding can change the final count.

[Source](../../kara_templater/sampling.py#L135)

```python
SamplingEstimate(
    target_samples: int,
    layer_intervals: int,
    estimated_events: int,
    step_ms: int,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `target_samples` | `int` | `required` |
| `layer_intervals` | `int` | `required` |
| `estimated_events` | `int` | `required` |
| `step_ms` | `int` | `required` |

## SamplingPlan

Prepared without calling user code. Inspect estimate before evaluate().

[Source](../../kara_templater/sampling.py#L148)

```python
SamplingPlan(
    effect: DynamicEffect,
    intervals: tuple[tuple[TextLayer, int, int, int], ...],
    estimate: SamplingEstimate,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `effect` | `DynamicEffect` | `required` |
| `intervals` | `tuple[tuple[TextLayer, int, int, int], ...]` | `required` |
| `estimate` | `SamplingEstimate` | `required` |

### SamplingPlan.evaluate

Evaluate a validated sampling plan and return its sampled text layers.

```python
SamplingPlan.evaluate() -> tuple[TextLayer, ...]
```

## SamplingSettings

A positive millisecond sampling step and total target-sample limit for native Track callbacks.

Editable Scene output instead uses SceneBudget.

[Source](../../kara_templater/sampling.py#L92)

```python
SamplingSettings(
    step_ms: int = 40,
    max_samples: int = 100000,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `step_ms` | `int` | `40` |
| `max_samples` | `int` | `100000` |

## ScaleAnimation

A resolved target scale schedule with millisecond boundaries and an explicit pivot.

Optional piecewise keyframes and keep behavior control evaluation beyond the
rise/fall interval.

[Source](../../kara_templater/animation.py#L189)

```python
ScaleAnimation(
    target_id: str,
    track_id: str,
    round_id: int,
    start_ms: float,
    end_ms: float,
    peak_scale: float,
    pivot: tuple[float, float],
    keyframes: tuple[tuple[float, float], ...] | None = None,
    keep: bool = False,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `target_id` | `str` | `required` |
| `track_id` | `str` | `required` |
| `round_id` | `int` | `required` |
| `start_ms` | `float` | `required` |
| `end_ms` | `float` | `required` |
| `peak_scale` | `float` | `required` |
| `pivot` | `tuple[float, float]` | `required` |
| `keyframes` | `tuple[tuple[float, float], ...] \| None` | `None` |
| `keep` | `bool` | `False` |

### ScaleAnimation.point_at

Transform a point around this animation pivot at a millisecond time.

```python
ScaleAnimation.point_at(
    x: float,
    y: float,
    time_ms: float,
) -> tuple[float, float]
```

### ScaleAnimation.points

The effective millisecond scale keyframes for this animation.

Type: `tuple[tuple[float, float], ...]`.

### ScaleAnimation.scale_at

Evaluate the resolved uniform scale at a millisecond time.

```python
ScaleAnimation.scale_at(
    time_ms: float,
) -> float
```

## SegmentStart

Trigger once for each original singing segment, including repeated readings.

[Source](../../kara_templater/animation.py#L56)

```python
SegmentStart()
```

## SingingPass

One traversal of a body region, optionally part of an explicit repeat round.

[Source](../../kara_templater/timeline.py#L132)

```python
SingingPass(
    start_ms: int,
    end_ms: int,
    region: Region,
    curve: ProgressCurve = ProgressCurve(knots=((0, 0), (1, 1))),
    round_id: int = 0,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `start_ms` | `int` | `required` |
| `end_ms` | `int` | `required` |
| `region` | `Region` | `required` |
| `curve` | `ProgressCurve` | `ProgressCurve(knots=((0, 0), (1, 1)))` |
| `round_id` | `int` | `0` |

### SingingPass.arrival

Invert this pass to find when its cursor reaches a script-space position.

```python
SingingPass.arrival(
    x: float,
) -> float | None
```

### SingingPass.position_at

Evaluate the sweep cursor in script pixels at a millisecond time.

```python
SingingPass.position_at(
    time_ms: float,
) -> float
```

### SingingPass.progress_at

Evaluate normalized singing progress at an absolute millisecond time.

```python
SingingPass.progress_at(
    time_ms: float,
) -> float
```

## SyllableStart

Trigger from the first singing segment of a source syllable.

[Source](../../kara_templater/animation.py#L51)

```python
SyllableStart()
```

## TextLayer

A low-level positioned text drawing with paint, millisecond clocks, clipping, and native animations.

active_window restricts exposure without changing its original fade or animation
clocks.

[Source](../../kara_templater/ass_output.py#L177)

```python
TextLayer(
    source_id: str,
    text: str,
    style: Style,
    box: Box,
    window: DisplayWindow,
    paint: Paint = _HAS_DEFAULT_FACTORY_CLASS(),
    fade: Fade = Fade(in_ms=0, out_ms=0),
    clips: tuple[ClipSpan, ...] | None = None,
    animations: tuple[ScaleAnimation, ...] = (),
    order: int = 0,
    animation_id: str | None = None,
    active_window: DisplayWindow | None = None,
    origin: EventOrigin | None = None,
    component: Literal['both', 'fill', 'glow'] = 'both',
    fade_window: DisplayWindow | None = None,
    opacity_animations: tuple[OpacityAnimation, ...] = (),
    offsets: tuple[OffsetAnimation, ...] = (),
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `source_id` | `str` | `required` |
| `text` | `str` | `required` |
| `style` | `Style` | `required` |
| `box` | `Box` | `required` |
| `window` | `DisplayWindow` | `required` |
| `paint` | `Paint` | `Paint()` |
| `fade` | `Fade` | `Fade(in_ms=0, out_ms=0)` |
| `clips` | `tuple[ClipSpan, ...] \| None` | `None` |
| `animations` | `tuple[ScaleAnimation, ...]` | `()` |
| `order` | `int` | `0` |
| `animation_id` | `str \| None` | `None` |
| `active_window` | `DisplayWindow \| None` | `None` |
| `origin` | `EventOrigin \| None` | `None` |
| `component` | `Literal['both', 'fill', 'glow']` | `'both'` |
| `fade_window` | `DisplayWindow \| None` | `None` |
| `opacity_animations` | `tuple[OpacityAnimation, ...]` | `()` |
| `offsets` | `tuple[OffsetAnimation, ...]` | `()` |

### TextLayer.pass_count

Number of paint passes emitted for each compiled interval.

Type: `int`.

## compile_layers

Compile typed text layers to standard ASS events without modifying a Document.

Enforce native output limits and return per-event origins and approximation
diagnostics.

[Source](../../kara_templater/ass_output.py#L645)

```python
compile_layers(
    layers: Iterable[TextLayer],
    *,
    settings: OutputSettings = OutputSettings(resolution=(1920, 1080), max_events=10000, clip_error_px=0.25, raster=None),
) -> CompiledLayers
```

## plan_pulses

Resolve triggers and reject conflicting scale animations.

Thresholds use the original character region. A threshold outside a track's
mapped body is not crossed. First-arrival selection is per target/round and
independent of visual track priority. Truncation retains original animation
times so clipping a display window never restarts or accelerates a pulse.
check_conflicts=False delegates overlap validation to a property composition
planner, which must validate the resulting intervals before output.

[Source](../../kara_templater/animation.py#L267)

```python
plan_pulses(
    pulses: tuple[Pulse, ...],
    *,
    layout: LaidOutLine,
    characters: tuple[CharacterTarget, ...],
    tracks: tuple[HighlightTrack, ...],
    window: DisplayWindow,
    overflow: str = 'truncate',
    check_conflicts: bool = True,
) -> AnimationPlan
```

## prepare_sampling

Compute cost and reject budgets before any property function evaluation.

Values are held constant over each absolute-grid bucket. Native fades, pulse
timing and sweep interpolation retain global time within the bucket. The
estimate counts bucket/pass exposures; native clip refinements can add more
events and remain subject to the output compiler's actual event limit.

[Source](../../kara_templater/sampling.py#L309)

```python
prepare_sampling(
    layers: Iterable[TextLayer],
    effect: DynamicEffect,
    *,
    max_events: int = 10000,
) -> SamplingPlan
```

## sweep_spans

One traversal including decoration transitions and post-singing hold.

[Source](../../kara_templater/ass_output.py#L143)

```python
sweep_spans(
    singing: SingingPass,
    *,
    paint: Region,
    window: DisplayWindow,
    edges: EdgeSweep = EdgeSweep(padding_px=0, lead_ms=0, tail_ms=0),
) -> tuple[ClipSpan, ...]
```

## tracks_from_layout

Use layout's ruby-weighted partitions as explicitly approximate body regions.

Static units have no track. Empty-reading partitions retain their duration
without contributing spatial coverage. Custom/repeated mappings use passes
supplied by the caller instead.

[Source](../../kara_templater/timeline.py#L283)

```python
tracks_from_layout(
    layout: LaidOutLine,
) -> tuple[HighlightTrack, ...]
```

## union_regions

Merge coverage without filling gaps or painting overlaps twice.

[Source](../../kara_templater/timeline.py#L214)

```python
union_regions(
    regions: Iterable[Region],
) -> tuple[Region, ...]
```
