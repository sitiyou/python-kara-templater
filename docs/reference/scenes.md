# Scenes and compilation

Scene lifetimes and evaluation use seconds; geometry uses script pixels. Compile returns a new Document under explicit resource limits. See [objects](../guides/objects.md) and [compilation](../guides/compilation.md).

[All public symbols](README.md#symbol-index)

## Contents

- [AssBudget](#assbudget)
- [AssDialogue](#assdialogue)
- [AssEstimate](#assestimate)
- [AssObjectReport](#assobjectreport)
- [AssResult](#assresult)
- [Lifetime](#lifetime)
- [ObjectGroup](#objectgroup)
- [PathObject](#pathobject)
- [PreparedHook](#preparedhook)
- [RectangleClip](#rectangleclip)
- [RectangleFunction](#rectanglefunction)
- [RectangleKeyframes](#rectanglekeyframes)
- [Scene](#scene)
- [SceneCompileError](#scenecompileerror)
- [SceneEvaluator](#sceneevaluator)
- [SceneObject](#sceneobject)
- [SceneReferenceError](#scenereferenceerror)
- [TextObject](#textobject)
- [VectorClip](#vectorclip)
- [VisualNode](#visualnode)

## AssBudget

Positive whole-scene ASS resource limits.

ASS compilation enforces limits on events, bytes, active drawings, geometry
and boolean work. It does not sample at fps or generate paint bands.
clip_error_px bounds known native rectangle-edge interpolation in screen
pixels, including endpoint rounding, before renderer pixel quantization.

[Source](../../kara_templater/output/ass_export.py#L61)

```python
AssBudget(
    *,
    max_events: int = 25000,
    max_bytes: int = 10485760,
    max_active: int = 1000,
    max_path_points: int = 4096,
    max_boolean_work: int = 1000000,
    clip_error_px: float = 0.75,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `max_events` | `int` | `25000` |
| `max_bytes` | `int` | `10485760` |
| `max_active` | `int` | `1000` |
| `max_path_points` | `int` | `4096` |
| `max_boolean_work` | `int` | `1000000` |
| `clip_error_px` | `float` | `0.75` |

## AssDialogue

Already-lowered Dialogue, including historical empty/negative intervals.

Native timing follows Document serialization (negative times clamp to zero),
rather than the positive display lifetime required by new visual objects.

[Source](../../kara_templater/scene.py#L558)

```python
AssDialogue(
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

## AssEstimate

Estimated ASS event count before emission.

[Source](../../kara_templater/output/ass_export.py#L93)

```python
AssEstimate(
    estimated_events: int,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `estimated_events` | `int` | `required` |

## AssObjectReport

ASS lowering strategy, source origin, event count and observed geometry costs.

[Source](../../kara_templater/output/ass_export.py#L100)

```python
AssObjectReport(
    id: str,
    strategy: str,
    events: int,
    origin: EventOrigin | None,
    peak_path_points: int | None = None,
    peak_clip_points: int | None = None,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `id` | `str` | `required` |
| `strategy` | `str` | `required` |
| `events` | `int` | `required` |
| `origin` | `EventOrigin \| None` | `required` |
| `peak_path_points` | `int \| None` | `None` |
| `peak_clip_points` | `int \| None` | `None` |

## AssResult

A newly compiled ASS Document with object reports, final cost metrics, diagnostics, and actual generated-event origins.

Caller-owned input objects remain unchanged.

[Source](../../kara_templater/output/ass_export.py#L112)

```python
AssResult(
    document: Document,
    objects: tuple[ass_export.AssObjectReport, ...],
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
| `objects` | `tuple[ass_export.AssObjectReport, ...]` | `required` |
| `event_count` | `int` | `required` |
| `peak_active` | `int` | `required` |
| `byte_count` | `int` | `required` |
| `estimated_events` | `int` | `required` |
| `max_time_quantization` | `float` | `required` |
| `diagnostics` | `tuple[str, ...]` | `()` |
| `event_origins` | `tuple[tuple[Line, EventOrigin \| None], ...]` | `()` |

## Lifetime

An absolute half-open seconds interval with 0 <= start < end.

Parent lifetimes further restrict child visibility without changing local
animation clocks.

[Source](../../kara_templater/scene.py#L57)

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

## ObjectGroup

Local child coordinates; absolute lifetimes intersect parent lifetimes.

Opacity is inherited per child, not offscreen compositing of the group.
Group paint is not inherited; use explicit child appearances instead.
Hook output supports normal screen-space rectangle clips with static
bounds or RectangleKeyframes evaluated on the group's clock. A parent
rectangle intersects child clips without replacing their local clocks.

[Source](../../kara_templater/scene.py#L471)

```python
ObjectGroup(
    *,
    id: str,
    lifetime: Lifetime,
    state: VisualState = VisualState(position=Vec2(x=0, y=0), scale=Vec2(x=1, y=1), rotation=0, skew=Vec2(x=0, y=0), opacity=1, fill=Color(red=255, green=255, blue=255), outline=Color(red=0, green=0, blue=0), border=0, blur=0, shadow=Vec2(x=0, y=0), shadow_opacity=1, face_opacity=1),
    clock_start: float | None = None,
    animations: tuple[AnimationClip, ...] = (),
    layer: int = 0,
    origin: EventOrigin | None = None,
    clip: RectangleClip | VectorClip | None = None,
    material: LinearGradient | None = None,
    reference: StateReference | None = None,
    children: tuple[SceneObject, ...],
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `id` | `str` | `required` |
| `lifetime` | `Lifetime` | `required` |
| `state` | `VisualState` | `VisualState(position=Vec2(x=0, y=0), scale=Vec2(x=1, y=1), rotation=0, skew=Vec2(x=0, y=0), opacity=1, fill=Color(red=255, green=255, blue=255), outline=Color(red=0, green=0, blue=0), border=0, blur=0, shadow=Vec2(x=0, y=0), shadow_opacity=1, face_opacity=1)` |
| `clock_start` | `float \| None` | `None` |
| `animations` | `tuple[AnimationClip, ...]` | `()` |
| `layer` | `int` | `0` |
| `origin` | `EventOrigin \| None` | `None` |
| `clip` | `RectangleClip \| VectorClip \| None` | `None` |
| `material` | `LinearGradient \| None` | `None` |
| `reference` | `StateReference \| None` | `None` |
| `children` | `tuple[SceneObject, ...]` | `required` |

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

## PathObject

A visual VectorPath drawing with state, lifetime, and optional geometry deformation.

Coordinates are local to its local origin and parent transforms. Set filled=False
for an outline-only drawing. The border radius uses script pixels by default.
With scale_border=True the radius is measured in local path coordinates.

[Source](../../kara_templater/scene.py#L429)

```python
PathObject(
    *,
    id: str,
    lifetime: Lifetime,
    state: VisualState = VisualState(position=Vec2(x=0, y=0), scale=Vec2(x=1, y=1), rotation=0, skew=Vec2(x=0, y=0), opacity=1, fill=Color(red=255, green=255, blue=255), outline=Color(red=0, green=0, blue=0), border=0, blur=0, shadow=Vec2(x=0, y=0), shadow_opacity=1, face_opacity=1),
    clock_start: float | None = None,
    animations: tuple[AnimationClip, ...] = (),
    layer: int = 0,
    origin: EventOrigin | None = None,
    clip: RectangleClip | VectorClip | None = None,
    material: LinearGradient | None = None,
    reference: StateReference | None = None,
    path: VectorPath,
    deform: GeometryAnimation | None = None,
    filled: bool = True,
    scale_border: bool = False,
    shader_paint: ShaderPaint | None = None,
    material_effects: tuple[MaterialClip, ...] = (),
    extrusion: Extrusion | None = None,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `id` | `str` | `required` |
| `lifetime` | `Lifetime` | `required` |
| `state` | `VisualState` | `VisualState(position=Vec2(x=0, y=0), scale=Vec2(x=1, y=1), rotation=0, skew=Vec2(x=0, y=0), opacity=1, fill=Color(red=255, green=255, blue=255), outline=Color(red=0, green=0, blue=0), border=0, blur=0, shadow=Vec2(x=0, y=0), shadow_opacity=1, face_opacity=1)` |
| `clock_start` | `float \| None` | `None` |
| `animations` | `tuple[AnimationClip, ...]` | `()` |
| `layer` | `int` | `0` |
| `origin` | `EventOrigin \| None` | `None` |
| `clip` | `RectangleClip \| VectorClip \| None` | `None` |
| `material` | `LinearGradient \| None` | `None` |
| `reference` | `StateReference \| None` | `None` |
| `path` | `VectorPath` | `required` |
| `deform` | `GeometryAnimation \| None` | `None` |
| `filled` | `bool` | `True` |
| `scale_border` | `bool` | `False` |
| `shader_paint` | `ShaderPaint \| None` | `None` |
| `material_effects` | `tuple[MaterialClip, ...]` | `()` |
| `extrusion` | `Extrusion \| None` | `None` |

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

## PreparedHook

Reusable snapshot for sequential exports at arbitrary positions and frame rates.

Prepare a new snapshot after changing the scene. Window exports share measured
masks and the resolved object hierarchy. Each output has its own playback clock.

[Source](../../kara_templater/scene.py#L644)

```python
PreparedHook(
    scene: Scene,
)
```

### PreparedHook.export

Write a standalone libplacebo .hook for a constant-frame-rate video.

Export animation parameters. Unsupported animations raise a compile error.
Start is frame-aligned in seconds. mpv uses media PTS;
the sequential clock in FFmpeg begins at start. Duration defaults to the remaining Scene;
subsequent frames pass through. Render at the exported fps on an opaque
SDR video with matching aspect ratio. Includes glyph masks and effects.
max_bytes limits the complete file before replacing the destination.

```python
PreparedHook.export(
    path: str | pathlib.Path,
    *,
    fps: int = 60,
    start: float = 0,
    duration: float | None = None,
    max_bytes: int | None = None,
) -> None
```

### PreparedHook.export_resources

Publish binary textures and GLSL for a preview host to a new directory.

The clock and rendering contract match export(). Each .bin contains a
row-aligned texture with dimensions given by textures.json.

```python
PreparedHook.export_resources(
    directory: str | pathlib.Path,
    *,
    fps: int = 60,
    start: float = 0,
    duration: float | None = None,
) -> None
```

### PreparedHook.material_inputs

List the named material defaults across the prepared Scene.

Preview hosts can discover editable inputs before exporting a window.
The uniforms in each exported window depend on its visible materials.

```python
PreparedHook.material_inputs() -> dict[str, PaintValue]
```

## RectangleClip

A positive-area normal or inverse rectangle in screen or object-local space.

Optional deformation evaluates local seconds and can produce an empty mask.

[Source](../../kara_templater/scene.py#L175)

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

[Source](../../kara_templater/scene.py#L78)

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

[Source](../../kara_templater/scene.py#L105)

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

A Document-backed composition of visual objects and already-lowered ASS dialogues.

add and source replacement configure generation; compile returns a new standard
ASS Document and reports.

[Source](../../kara_templater/scene.py#L576)

```python
Scene(
    document: Document,
    objects: list[SceneObject | AssDialogue] = _HAS_DEFAULT_FACTORY_CLASS(),
    replace_records: set[int] = _HAS_DEFAULT_FACTORY_CLASS(),
    owner: str = 'scene',
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `document` | `Document` | `required` |
| `objects` | `list[SceneObject \| AssDialogue]` | `list()` |
| `replace_records` | `set[int]` | `set()` |
| `owner` | `str` | `'scene'` |

### Scene.add

Append typed visual/native objects and return this Scene for composition.

```python
Scene.add(
    *objects: SceneObject | AssDialogue,
) -> Self
```

### Scene.ass

Access native ASS export for this scene.

Type: `AssOutput`.

### Scene.evaluator

Construct a seekable world-space evaluator for this scene hierarchy and its references.

```python
Scene.evaluator() -> SceneEvaluator
```

### Scene.export

Write a standalone libplacebo .hook for a constant-frame-rate video.

Export animation parameters. Unsupported animations raise a compile error.
Start is frame-aligned in seconds. mpv uses media PTS;
the sequential clock in FFmpeg begins at start. Duration defaults to the remaining Scene;
subsequent frames pass through. Render at the exported fps on an opaque
SDR video with matching aspect ratio. Includes glyph masks and effects.
max_bytes limits the complete file before replacing the destination.

```python
Scene.export(
    path: str | pathlib.Path,
    *,
    fps: int = 60,
    start: float = 0,
    duration: float | None = None,
    max_bytes: int | None = None,
) -> None
```

### Scene.export_resources

Publish binary textures and GLSL for a preview host to a new directory.

The clock and rendering contract match export(). Each .bin contains a
row-aligned texture with dimensions given by textures.json.

```python
Scene.export_resources(
    directory: str | pathlib.Path,
    *,
    fps: int = 60,
    start: float = 0,
    duration: float | None = None,
) -> None
```

### Scene.prepare_hook

Snapshot the scene for repeated window exports with a shared glyph cache.

```python
Scene.prepare_hook() -> PreparedHook
```

### Scene.replace_source

Mark a valid source event record for retention as a Comment during compilation.

```python
Scene.replace_source(
    record_index: int,
) -> None
```

## SceneCompileError

An invalid scene or exceeded compilation limit with object_id and optional source origin.

Callback causes remain available for diagnosis.

[Source](../../kara_templater/scene.py#L41)

```python
SceneCompileError(
    message: str,
    *,
    object_id: str = '',
    origin: EventOrigin | None = None,
)
```

## SceneEvaluator

Immutable object snapshot; no previous-frame state or cross-call cache.

[Source](../../kara_templater/scene_evaluation.py#L76)

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

[Source](../../kara_templater/scene.py#L384)

```python
TextObject(
    *,
    id: str,
    lifetime: Lifetime,
    state: VisualState = VisualState(position=Vec2(x=0, y=0), scale=Vec2(x=1, y=1), rotation=0, skew=Vec2(x=0, y=0), opacity=1, fill=Color(red=255, green=255, blue=255), outline=Color(red=0, green=0, blue=0), border=0, blur=0, shadow=Vec2(x=0, y=0), shadow_opacity=1, face_opacity=1),
    clock_start: float | None = None,
    animations: tuple[AnimationClip, ...] = (),
    layer: int = 0,
    origin: EventOrigin | None = None,
    clip: RectangleClip | VectorClip | None = None,
    material: LinearGradient | None = None,
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
    shader_paint: ShaderPaint | None = None,
    material_effects: tuple[MaterialClip, ...] = (),
    extrusion: Extrusion | None = None,
    filled: bool = True,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `id` | `str` | `required` |
| `lifetime` | `Lifetime` | `required` |
| `state` | `VisualState` | `VisualState(position=Vec2(x=0, y=0), scale=Vec2(x=1, y=1), rotation=0, skew=Vec2(x=0, y=0), opacity=1, fill=Color(red=255, green=255, blue=255), outline=Color(red=0, green=0, blue=0), border=0, blur=0, shadow=Vec2(x=0, y=0), shadow_opacity=1, face_opacity=1)` |
| `clock_start` | `float \| None` | `None` |
| `animations` | `tuple[AnimationClip, ...]` | `()` |
| `layer` | `int` | `0` |
| `origin` | `EventOrigin \| None` | `None` |
| `clip` | `RectangleClip \| VectorClip \| None` | `None` |
| `material` | `LinearGradient \| None` | `None` |
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
| `shader_paint` | `ShaderPaint \| None` | `None` |
| `material_effects` | `tuple[MaterialClip, ...]` | `()` |
| `extrusion` | `Extrusion \| None` | `None` |
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

[Source](../../kara_templater/scene.py#L224)

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

[Source](../../kara_templater/scene.py#L246)

```python
VisualNode(
    *,
    id: str,
    lifetime: Lifetime,
    state: VisualState = VisualState(position=Vec2(x=0, y=0), scale=Vec2(x=1, y=1), rotation=0, skew=Vec2(x=0, y=0), opacity=1, fill=Color(red=255, green=255, blue=255), outline=Color(red=0, green=0, blue=0), border=0, blur=0, shadow=Vec2(x=0, y=0), shadow_opacity=1, face_opacity=1),
    clock_start: float | None = None,
    animations: tuple[AnimationClip, ...] = (),
    layer: int = 0,
    origin: EventOrigin | None = None,
    clip: RectangleClip | VectorClip | None = None,
    material: LinearGradient | None = None,
    reference: StateReference | None = None,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `id` | `str` | `required` |
| `lifetime` | `Lifetime` | `required` |
| `state` | `VisualState` | `VisualState(position=Vec2(x=0, y=0), scale=Vec2(x=1, y=1), rotation=0, skew=Vec2(x=0, y=0), opacity=1, fill=Color(red=255, green=255, blue=255), outline=Color(red=0, green=0, blue=0), border=0, blur=0, shadow=Vec2(x=0, y=0), shadow_opacity=1, face_opacity=1)` |
| `clock_start` | `float \| None` | `None` |
| `animations` | `tuple[AnimationClip, ...]` | `()` |
| `layer` | `int` | `0` |
| `origin` | `EventOrigin \| None` | `None` |
| `clip` | `RectangleClip \| VectorClip \| None` | `None` |
| `material` | `LinearGradient \| None` | `None` |
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
