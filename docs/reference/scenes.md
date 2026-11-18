# Scenes and compilation

Scene lifetimes and evaluation use seconds; geometry uses script pixels. Compile returns a new Document under explicit resource limits. See [objects](../guides/objects.md) and [compilation](../guides/compilation.md).

[All public symbols](README.md#symbol-index)

## Contents

- [CoverageEstimate](#coverageestimate)
- [Lifetime](#lifetime)
- [NativeEvent](#nativeevent)
- [ObjectGroup](#objectgroup)
- [ObjectReport](#objectreport)
- [PathObject](#pathobject)
- [RectangleClip](#rectangleclip)
- [RectangleFunction](#rectanglefunction)
- [RectangleKeyframes](#rectanglekeyframes)
- [Scene](#scene)
- [SceneBudget](#scenebudget)
- [SceneCompileError](#scenecompileerror)
- [SceneEstimate](#sceneestimate)
- [SceneEvaluator](#sceneevaluator)
- [SceneObject](#sceneobject)
- [SceneReferenceError](#scenereferenceerror)
- [SceneResult](#sceneresult)
- [TextObject](#textobject)
- [VectorClip](#vectorclip)
- [VisualNode](#visualnode)
- [compile_scene](#compile_scene)
- [render_enhanced](#render_enhanced)

## CoverageEstimate

Callback-free coverage work counts, before pixels or ASS rectangles exist.

frames includes declared breakpoints; target_samples is frames times drawable
leaves. Neither predicts encoded event count, memory use, or elapsed time.

[Source](../../kara_templater/scene_output.py#L116)

```python
CoverageEstimate(
    id: str,
    frames: int,
    target_samples: int,
    max_channel_error: int,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `id` | `str` | `required` |
| `frames` | `int` | `required` |
| `target_samples` | `int` | `required` |
| `max_channel_error` | `int` | `required` |

## Lifetime

An absolute half-open seconds interval with 0 <= start < end.

Parent lifetimes further restrict child visibility without changing local
animation clocks.

[Source](../../kara_templater/scene.py#L34)

```python
Lifetime(
    start: float,
    end: float,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `start` | `float` | `required` |
| `end` | `float` | `required` |

### Lifetime.contains

Whether an absolute seconds time lies in this half-open lifetime.

```python
Lifetime.contains(
    time: float,
) -> bool
```

## NativeEvent

Already-lowered Dialogue, including historical empty/negative intervals.

Native timing follows Document serialization (negative times clamp to zero),
rather than the positive display lifetime required by new visual objects.

[Source](../../kara_templater/scene.py#L516)

```python
NativeEvent(
    id: str,
    event: Line,
    origin: EventOrigin | None = None,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `id` | `str` | `required` |
| `event` | `Line` | `required` |
| `origin` | `EventOrigin \| None` | `None` |

## ObjectGroup

Local child coordinates; absolute lifetimes intersect parent lifetimes.

Opacity is inherited per child, not offscreen compositing of the group.
Group paint is not inherited; use explicit child appearances instead.

[Source](../../kara_templater/scene.py#L424)

```python
ObjectGroup(
    *,
    id: str,
    lifetime: Lifetime,
    state: VisualState = VisualState(position=Vec2(x=0, y=0), scale=Vec2(x=1, y=1), rotation=0, skew=Vec2(x=0, y=0), opacity=1, fill=Color(red=255, green=255, blue=255), outline=Color(red=0, green=0, blue=0), border=0, blur=0, shadow=Vec2(x=0, y=0)),
    clock_start: float | None = None,
    animations: tuple[AnimationClip, ...] = (),
    layer: int = 0,
    origin: EventOrigin | None = None,
    clip: RectangleClip | VectorClip | None = None,
    material: PaintField | None = None,
    reference: StateReference | None = None,
    children: tuple[SceneObject, ...],
    coverage: Coverage | None = None,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `id` | `str` | `required` |
| `lifetime` | `Lifetime` | `required` |
| `state` | `VisualState` | `VisualState(position=Vec2(x=0, y=0), scale=Vec2(x=1, y=1), rotation=0, skew=Vec2(x=0, y=0), opacity=1, fill=Color(red=255, green=255, blue=255), outline=Color(red=0, green=0, blue=0), border=0, blur=0, shadow=Vec2(x=0, y=0))` |
| `clock_start` | `float \| None` | `None` |
| `animations` | `tuple[AnimationClip, ...]` | `()` |
| `layer` | `int` | `0` |
| `origin` | `EventOrigin \| None` | `None` |
| `clip` | `RectangleClip \| VectorClip \| None` | `None` |
| `material` | `PaintField \| None` | `None` |
| `reference` | `StateReference \| None` | `None` |
| `children` | `tuple[SceneObject, ...]` | `required` |
| `coverage` | `Coverage \| None` | `None` |

### ObjectGroup.animate

Return a new node with an animation bound at local seconds from birth.

The same operation works on text, paths and groups. Existing clips are
preserved; conflicting channels or a clip beyond the lifetime raise
before changing anything. Use a timeline for longer schedules.

```python
ObjectGroup.animate(
    animation: StateAnimation,
    *,
    duration: float,
    at: float = 0,
    hold: bool = True,
    breakpoints: tuple[float, ...] = (),
) -> Self
```

### ObjectGroup.at

Evaluate this object at absolute seconds using its local animation clock.

Use SceneEvaluator for parent transforms and references.

```python
ObjectGroup.at(
    time: float,
) -> VisualState
```

### ObjectGroup.copy

Copy the full hierarchy with unique identities, delayed local clocks, and remapped internal references.

```python
ObjectGroup.copy(
    *,
    id: str,
    offset: Vec2 | None = None,
    delay: float = 0,
) -> Self
```

### ObjectGroup.time_origin

Absolute seconds origin for local animation, geometry and paint clocks.

Type: `float`.

## ObjectReport

Per-object output strategy, event count, source origin, sample interval, and observed geometry/band costs.

Optional metrics apply only to relevant strategies.

[Source](../../kara_templater/scene_output.py#L143)

```python
ObjectReport(
    id: str,
    strategy: str,
    events: int,
    origin: EventOrigin | None,
    sample_interval: float | None = None,
    peak_path_points: int | None = None,
    peak_bands: int | None = None,
    peak_clip_points: int | None = None,
    sample_times: tuple[float, ...] = (),
    max_channel_error: int = 0,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `id` | `str` | `required` |
| `strategy` | `str` | `required` |
| `events` | `int` | `required` |
| `origin` | `EventOrigin \| None` | `required` |
| `sample_interval` | `float \| None` | `None` |
| `peak_path_points` | `int \| None` | `None` |
| `peak_bands` | `int \| None` | `None` |
| `peak_clip_points` | `int \| None` | `None` |
| `sample_times` | `tuple[float, ...]` | `()` |
| `max_channel_error` | `int` | `0` |

## PathObject

A visual VectorPath drawing with state, lifetime, and optional geometry deformation.

Coordinates are local to its local origin and parent transforms. Set filled=False
for an outline-only drawing; border sets the outline radius in script pixels.

[Source](../../kara_templater/scene.py#L387)

```python
PathObject(
    *,
    id: str,
    lifetime: Lifetime,
    state: VisualState = VisualState(position=Vec2(x=0, y=0), scale=Vec2(x=1, y=1), rotation=0, skew=Vec2(x=0, y=0), opacity=1, fill=Color(red=255, green=255, blue=255), outline=Color(red=0, green=0, blue=0), border=0, blur=0, shadow=Vec2(x=0, y=0)),
    clock_start: float | None = None,
    animations: tuple[AnimationClip, ...] = (),
    layer: int = 0,
    origin: EventOrigin | None = None,
    clip: RectangleClip | VectorClip | None = None,
    material: PaintField | None = None,
    reference: StateReference | None = None,
    path: VectorPath,
    deform: GeometryAnimation | None = None,
    filled: bool = True,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `id` | `str` | `required` |
| `lifetime` | `Lifetime` | `required` |
| `state` | `VisualState` | `VisualState(position=Vec2(x=0, y=0), scale=Vec2(x=1, y=1), rotation=0, skew=Vec2(x=0, y=0), opacity=1, fill=Color(red=255, green=255, blue=255), outline=Color(red=0, green=0, blue=0), border=0, blur=0, shadow=Vec2(x=0, y=0))` |
| `clock_start` | `float \| None` | `None` |
| `animations` | `tuple[AnimationClip, ...]` | `()` |
| `layer` | `int` | `0` |
| `origin` | `EventOrigin \| None` | `None` |
| `clip` | `RectangleClip \| VectorClip \| None` | `None` |
| `material` | `PaintField \| None` | `None` |
| `reference` | `StateReference \| None` | `None` |
| `path` | `VectorPath` | `required` |
| `deform` | `GeometryAnimation \| None` | `None` |
| `filled` | `bool` | `True` |

### PathObject.animate

Return a new node with an animation bound at local seconds from birth.

The same operation works on text, paths and groups. Existing clips are
preserved; conflicting channels or a clip beyond the lifetime raise
before changing anything. Use a timeline for longer schedules.

```python
PathObject.animate(
    animation: StateAnimation,
    *,
    duration: float,
    at: float = 0,
    hold: bool = True,
    breakpoints: tuple[float, ...] = (),
) -> Self
```

### PathObject.at

Evaluate this object at absolute seconds using its local animation clock.

Use SceneEvaluator for parent transforms and references.

```python
PathObject.at(
    time: float,
) -> VisualState
```

### PathObject.copy

Independent immutable object; animation clocks stay relative to birth.

```python
PathObject.copy(
    *,
    id: str,
    offset: Vec2 | None = None,
    delay: float = 0,
) -> Self
```

### PathObject.path_at

Return the original or deformed path at absolute seconds, using the object birth as local origin.

```python
PathObject.path_at(
    time: float,
) -> VectorPath | None
```

### PathObject.time_origin

Absolute seconds origin for local animation, geometry and paint clocks.

Type: `float`.

## RectangleClip

A positive-area normal or inverse rectangle in screen or object-local space.

Optional deformation evaluates local seconds and can produce an empty mask.

[Source](../../kara_templater/scene.py#L145)

```python
RectangleClip(
    left: float,
    top: float,
    right: float,
    bottom: float,
    inverse: bool = False,
    space: Literal['screen', 'local'] = 'screen',
    deform: RectangleFunction | RectangleKeyframes | None = None,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `left` | `float` | `required` |
| `top` | `float` | `required` |
| `right` | `float` | `required` |
| `bottom` | `float` | `required` |
| `inverse` | `bool` | `False` |
| `space` | `Literal['screen', 'local']` | `'screen'` |
| `deform` | `RectangleFunction \| RectangleKeyframes \| None` | `None` |

## RectangleFunction

Pure signed-local-seconds rectangle bounds; None denotes an empty mask.

The owning object validates breakpoint times against its absolute clock.

[Source](../../kara_templater/scene.py#L55)

```python
RectangleFunction(
    function: Callable[[float], tuple[float, float, float, float] | None],
    breakpoints: tuple[float, ...] = (),
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `function` | `Callable[[float], tuple[float, float, float, float] \| None]` | `required` |
| `breakpoints` | `tuple[float, ...]` | `()` |

### RectangleFunction.sample

Evaluate local-seconds bounds; None represents an empty rectangle mask.

```python
RectangleFunction.sample(
    time: float,
) -> tuple[float, float, float, float] | None
```

## RectangleKeyframes

Known piecewise-linear rectangle bounds in signed local seconds.

Each keyframe is (time, (left, top, right, bottom)). End values hold outside
the key range. Two keys at the same time encode an instantaneous reset:
the first is the left limit and the second takes effect at that time.
Zero width or height is an empty mask, with its coordinates retained for
interpolation. The owning object validates absolute breakpoint times.

[Source](../../kara_templater/scene.py#L82)

```python
RectangleKeyframes(
    keyframes: tuple[tuple[float, tuple[float, float, float, float]], ...],
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `keyframes` | `tuple[tuple[float, tuple[float, float, float, float]], ...]` | `required` |

### RectangleKeyframes.bounds_at

Evaluate bounds; before selects the left limit at a reset boundary.

```python
RectangleKeyframes.bounds_at(
    time: float,
    *,
    before: bool = False,
) -> tuple[float, float, float, float]
```

### RectangleKeyframes.breakpoints

Distinct local key times, including instantaneous reset boundaries.

Type: `tuple[float, ...]`.

### RectangleKeyframes.sample

Evaluate the same mask protocol as RectangleFunction.

```python
RectangleKeyframes.sample(
    time: float,
) -> tuple[float, float, float, float] | None
```

## Scene

A Document-backed composition of visual objects and already-lowered NativeEvents.

add and source replacement configure generation; compile returns a new standard
ASS Document and reports.

[Source](../../kara_templater/scene.py#L534)

```python
Scene(
    document: Document,
    objects: list[SceneObject | NativeEvent] = _HAS_DEFAULT_FACTORY_CLASS(),
    replace_records: set[int] = _HAS_DEFAULT_FACTORY_CLASS(),
    owner: str = 'scene',
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `document` | `Document` | `required` |
| `objects` | `list[SceneObject \| NativeEvent]` | `list()` |
| `replace_records` | `set[int]` | `set()` |
| `owner` | `str` | `'scene'` |

### Scene.add

Append typed visual/native objects and return this Scene for composition.

```python
Scene.add(
    *objects: SceneObject | NativeEvent,
) -> Self
```

### Scene.compile

Compile a new ASS Document and reports under explicit Scene budgets.

Eligible continuous Tween lowering is opt-in.
on_estimate runs after preflight and before frame callbacks; raising
cancels compilation without changing the scene or source document.

```python
Scene.compile(
    *,
    budget: SceneBudget | None = None,
    native_tweens: bool = False,
    on_estimate: Callable[[SceneEstimate], None] | None = None,
) -> SceneResult
```

### Scene.enhance

Attach sampled GPU effects to an explicit ordinary-ASS fallback.

Returns a new Document with versioned private Comment records. Ordinary
players display fallback unchanged; render_enhanced replaces its visual
presentation with this complete Scene. Resolution must match. Existing
Python callbacks run at export only; portable data stores reusable glyph
masks and numeric draws at integer fps (1..240), not executable code.
This initial backend supports text/static paths, affine animation, normal
local/screen rectangle clips and continuous LinearGradient. Unsupported
materials, native events, coverage groups, inherited/vector/inverse clips
and deformed paths raise. Export has bounded frame/mask/payload budgets.

```python
Scene.enhance(
    fallback: Document,
    *,
    fps: int = 60,
) -> Document
```

### Scene.evaluator

Construct a seekable world-space evaluator for this scene hierarchy and its references.

```python
Scene.evaluator() -> SceneEvaluator
```

### Scene.export_hook

Write a standalone libplacebo .hook for a constant-frame-rate video.

Export animation parameters and sample unsupported intervals on the fps grid.
Start is frame-aligned in seconds. mpv uses media PTS;
the sequential clock in FFmpeg begins at start. Duration defaults to the remaining Scene;
subsequent frames pass through. Render at the exported fps on an opaque
SDR video with matching aspect ratio. Includes glyph masks and effects.

```python
Scene.export_hook(
    path: str | pathlib.Path,
    *,
    fps: int = 60,
    start: float = 0,
    duration: float | None = None,
) -> None
```

### Scene.replace_source

Mark a valid source event record for retention as a Comment during compilation.

```python
Scene.replace_source(
    record_index: int,
) -> None
```

## SceneBudget

Positive whole-scene sampling and resource limits.

Defaults bound events, bytes, active drawings, geometry, color bands, and
boolean work; exceeding a limit raises instead of reducing quality.
clip_error_px bounds known native rectangle-edge interpolation in screen
pixels, including endpoint rounding, before renderer pixel quantization.

[Source](../../kara_templater/scene_output.py#L76)

```python
SceneBudget(
    *,
    fps: int = 50,
    max_events: int = 25000,
    max_bytes: int = 10485760,
    max_active: int = 1000,
    max_path_points: int = 4096,
    max_bands: int = 1024,
    max_boolean_work: int = 1000000,
    clip_error_px: float = 0.75,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `fps` | `int` | `50` |
| `max_events` | `int` | `25000` |
| `max_bytes` | `int` | `10485760` |
| `max_active` | `int` | `1000` |
| `max_path_points` | `int` | `4096` |
| `max_bands` | `int` | `1024` |
| `max_boolean_work` | `int` | `1000000` |
| `clip_error_px` | `float` | `0.75` |

## SceneCompileError

An invalid scene or exceeded compilation limit with object_id and optional source origin.

Callback causes remain available for diagnosis.

[Source](../../kara_templater/scene_output.py#L60)

```python
SceneCompileError(
    message: str,
    *,
    object_id: str = '',
    origin: EventOrigin | None = None,
)
```

## SceneEstimate

Immutable compilation preflight delivered before frame callbacks.

estimated_events counts ordinary/native output estimates, excluding coverage
rectangles whose count is unknown until rendering. coverage reports their
planned work separately. Final budgets still apply to all output.

[Source](../../kara_templater/scene_output.py#L130)

```python
SceneEstimate(
    estimated_events: int,
    coverage: tuple[CoverageEstimate, ...],
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `estimated_events` | `int` | `required` |
| `coverage` | `tuple[CoverageEstimate, ...]` | `required` |

## SceneEvaluator

Immutable object snapshot; no previous-frame state or cross-call cache.

[Source](../../kara_templater/scene_evaluation.py#L70)

```python
SceneEvaluator(
    scene: Scene,
)
```

### SceneEvaluator.at

Evaluate a node world state at absolute seconds independently of previous queries.

```python
SceneEvaluator.at(
    name: str,
    time: float,
) -> VisualState
```

### SceneEvaluator.breakpoints

Return declared absolute-seconds boundaries relevant to a node and its dependencies.

```python
SceneEvaluator.breakpoints(
    name: str,
) -> tuple[float, ...]
```

### SceneEvaluator.referenced

Whether a node has effective animation dependencies requiring world-state evaluation.

```python
SceneEvaluator.referenced(
    name: str,
) -> bool
```

## SceneObject

Public type alias:

```python
type SceneObject = TextObject | PathObject | ObjectGroup
```

## SceneReferenceError

An invalid dependency, reference cycle, or failed world-state evaluation.

object_id and optional origin locate the affected Scene object.

[Source](../../kara_templater/scene_evaluation.py#L13)

```python
SceneReferenceError(
    message: str,
    *,
    object_id: str,
    origin: EventOrigin | None = None,
)
```

## SceneResult

A newly compiled ASS Document with object reports, final cost metrics, diagnostics, and actual generated-event origins.

Caller-owned input objects remain unchanged.

[Source](../../kara_templater/scene_output.py#L162)

```python
SceneResult(
    document: Document,
    objects: tuple[ObjectReport, ...],
    event_count: int,
    peak_active: int,
    byte_count: int,
    estimated_events: int,
    max_time_quantization: float,
    diagnostics: tuple[str, ...] = (),
    event_origins: tuple[tuple[Line, EventOrigin | None], ...] = (),
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `document` | `Document` | `required` |
| `objects` | `tuple[ObjectReport, ...]` | `required` |
| `event_count` | `int` | `required` |
| `peak_active` | `int` | `required` |
| `byte_count` | `int` | `required` |
| `estimated_events` | `int` | `required` |
| `max_time_quantization` | `float` | `required` |
| `diagnostics` | `tuple[str, ...]` | `()` |
| `event_origins` | `tuple[tuple[Line, EventOrigin \| None], ...]` | `()` |

## TextObject

A text drawing with family name, pixel font size, shaping style, alignment, and inherited visual state.

Unsupported affine combinations can lower to glyph geometry with explicit
budgets. Text is literal Unicode: braces and backslashes are displayed,
not interpreted as ASS tags; newlines become hard line breaks. CR and NUL
are rejected. Set scale_border to scale the outline radius along each glyph
axis with the text. The default ASS outline radius uses script pixels.
Set filled=False for outline-only text.
For affine paths baked into screen coordinates, ASS approximates a sheared
or tilted elliptical outline using its horizontal and vertical radii.

[Source](../../kara_templater/scene.py#L345)

```python
TextObject(
    *,
    id: str,
    lifetime: Lifetime,
    state: VisualState = VisualState(position=Vec2(x=0, y=0), scale=Vec2(x=1, y=1), rotation=0, skew=Vec2(x=0, y=0), opacity=1, fill=Color(red=255, green=255, blue=255), outline=Color(red=0, green=0, blue=0), border=0, blur=0, shadow=Vec2(x=0, y=0)),
    clock_start: float | None = None,
    animations: tuple[AnimationClip, ...] = (),
    layer: int = 0,
    origin: EventOrigin | None = None,
    clip: RectangleClip | VectorClip | None = None,
    material: PaintField | None = None,
    reference: StateReference | None = None,
    text: str,
    font: str = 'DejaVu Sans',
    font_size: float = 48,
    bold: bool = False,
    italic: bool = False,
    spacing: float = 0,
    alignment: int = 7,
    encoding: int = 1,
    scale_border: bool = False,
    filled: bool = True,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `id` | `str` | `required` |
| `lifetime` | `Lifetime` | `required` |
| `state` | `VisualState` | `VisualState(position=Vec2(x=0, y=0), scale=Vec2(x=1, y=1), rotation=0, skew=Vec2(x=0, y=0), opacity=1, fill=Color(red=255, green=255, blue=255), outline=Color(red=0, green=0, blue=0), border=0, blur=0, shadow=Vec2(x=0, y=0))` |
| `clock_start` | `float \| None` | `None` |
| `animations` | `tuple[AnimationClip, ...]` | `()` |
| `layer` | `int` | `0` |
| `origin` | `EventOrigin \| None` | `None` |
| `clip` | `RectangleClip \| VectorClip \| None` | `None` |
| `material` | `PaintField \| None` | `None` |
| `reference` | `StateReference \| None` | `None` |
| `text` | `str` | `required` |
| `font` | `str` | `'DejaVu Sans'` |
| `font_size` | `float` | `48` |
| `bold` | `bool` | `False` |
| `italic` | `bool` | `False` |
| `spacing` | `float` | `0` |
| `alignment` | `int` | `7` |
| `encoding` | `int` | `1` |
| `scale_border` | `bool` | `False` |
| `filled` | `bool` | `True` |

### TextObject.animate

Return a new node with an animation bound at local seconds from birth.

The same operation works on text, paths and groups. Existing clips are
preserved; conflicting channels or a clip beyond the lifetime raise
before changing anything. Use a timeline for longer schedules.

```python
TextObject.animate(
    animation: StateAnimation,
    *,
    duration: float,
    at: float = 0,
    hold: bool = True,
    breakpoints: tuple[float, ...] = (),
) -> Self
```

### TextObject.at

Evaluate this object at absolute seconds using its local animation clock.

Use SceneEvaluator for parent transforms and references.

```python
TextObject.at(
    time: float,
) -> VisualState
```

### TextObject.copy

Independent immutable object; animation clocks stay relative to birth.

```python
TextObject.copy(
    *,
    id: str,
    offset: Vec2 | None = None,
    delay: float = 0,
) -> Self
```

### TextObject.time_origin

Absolute seconds origin for local animation, geometry and paint clocks.

Type: `float`.

## VectorClip

A filled mask; deform uses object-local seconds. None is an empty region.

Empty normal masks hide the object; empty inverse masks reveal it entirely.
Local coordinates are relative to the object's alignment anchor.

[Source](../../kara_templater/scene.py#L168)

```python
VectorClip(
    path: VectorPath,
    inverse: bool = False,
    space: Literal['screen', 'local'] = 'screen',
    deform: GeometryAnimation | None = None,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `path` | `VectorPath` | `required` |
| `inverse` | `bool` | `False` |
| `space` | `Literal['screen', 'local']` | `'screen'` |
| `deform` | `GeometryAnimation \| None` | `None` |

## VisualNode

Common state, lifetime, animation, clip, material, reference, and source metadata for Scene visuals.

lifetime controls visibility. clock_start optionally preserves an absolute
local-time origin when visibility changes; otherwise the origin is
lifetime.start. Earlier visibility gives callbacks negative local seconds;
scheduled animations remain unstarted until their clip start.
Copies shift both visibility and an explicit clock origin.
Local evaluation is distinct from world-space SceneEvaluator queries.

[Source](../../kara_templater/scene.py#L190)

```python
VisualNode(
    *,
    id: str,
    lifetime: Lifetime,
    state: VisualState = VisualState(position=Vec2(x=0, y=0), scale=Vec2(x=1, y=1), rotation=0, skew=Vec2(x=0, y=0), opacity=1, fill=Color(red=255, green=255, blue=255), outline=Color(red=0, green=0, blue=0), border=0, blur=0, shadow=Vec2(x=0, y=0)),
    clock_start: float | None = None,
    animations: tuple[AnimationClip, ...] = (),
    layer: int = 0,
    origin: EventOrigin | None = None,
    clip: RectangleClip | VectorClip | None = None,
    material: PaintField | None = None,
    reference: StateReference | None = None,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `id` | `str` | `required` |
| `lifetime` | `Lifetime` | `required` |
| `state` | `VisualState` | `VisualState(position=Vec2(x=0, y=0), scale=Vec2(x=1, y=1), rotation=0, skew=Vec2(x=0, y=0), opacity=1, fill=Color(red=255, green=255, blue=255), outline=Color(red=0, green=0, blue=0), border=0, blur=0, shadow=Vec2(x=0, y=0))` |
| `clock_start` | `float \| None` | `None` |
| `animations` | `tuple[AnimationClip, ...]` | `()` |
| `layer` | `int` | `0` |
| `origin` | `EventOrigin \| None` | `None` |
| `clip` | `RectangleClip \| VectorClip \| None` | `None` |
| `material` | `PaintField \| None` | `None` |
| `reference` | `StateReference \| None` | `None` |

### VisualNode.animate

Return a new node with an animation bound at local seconds from birth.

The same operation works on text, paths and groups. Existing clips are
preserved; conflicting channels or a clip beyond the lifetime raise
before changing anything. Use a timeline for longer schedules.

```python
VisualNode.animate(
    animation: StateAnimation,
    *,
    duration: float,
    at: float = 0,
    hold: bool = True,
    breakpoints: tuple[float, ...] = (),
) -> Self
```

### VisualNode.at

Evaluate this object at absolute seconds using its local animation clock.

Use SceneEvaluator for parent transforms and references.

```python
VisualNode.at(
    time: float,
) -> VisualState
```

### VisualNode.copy

Independent immutable object; animation clocks stay relative to birth.

```python
VisualNode.copy(
    *,
    id: str,
    offset: Vec2 | None = None,
    delay: float = 0,
) -> Self
```

### VisualNode.time_origin

Absolute seconds origin for local animation, geometry and paint clocks.

Type: `float`.

## compile_scene

Return a new Document. Source records and caller-owned nodes never mutate.

[Source](../../kara_templater/scene_output.py#L1758)

```python
compile_scene(
    scene: Scene,
    *,
    budget: SceneBudget | None = None,
    native_tweens: bool = False,
    on_estimate: Callable[[SceneEstimate], None] | None = None,
) -> SceneResult
```

## render_enhanced

Burn an enhanced ASS into video with GPU coverage/gradient rendering.

Requires ModernGL, a working OpenGL 3.3 context and FFmpeg on PATH. Frames
stream as premultiplied RGBA to FFmpeg; video is encoded with libx264 and
optional input audio with AAC. Original audio/video timing is retained for
the selected interval, rebased to zero. Resolution/fps come from the payload.
Start must be on that frame grid; duration rounds up to a whole frame. Output
is atomically replaced only on success; existing files require overwrite.

[Source](../../kara_templater/gpu_render.py#L16)

```python
render_enhanced(
    document: Document,
    video: str | pathlib.Path,
    output: str | pathlib.Path,
    *,
    start: float = 0,
    duration: float | None = None,
    backend: str = 'egl',
    overwrite: bool = False,
) -> None
```
