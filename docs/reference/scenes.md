# Scenes and compilation

Scene lifetimes and evaluation use seconds; geometry uses script pixels. Compile returns a new Document under explicit resource limits. See [objects](../guides/objects.md) and [compilation](../guides/compilation.md).

[All public symbols](README.md#symbol-index)

## Contents

- [Lifetime](#lifetime)
- [NativeEvent](#nativeevent)
- [ObjectGroup](#objectgroup)
- [ObjectReport](#objectreport)
- [PathObject](#pathobject)
- [RectangleClip](#rectangleclip)
- [RectangleFunction](#rectanglefunction)
- [Scene](#scene)
- [SceneBudget](#scenebudget)
- [SceneCompileError](#scenecompileerror)
- [SceneEvaluator](#sceneevaluator)
- [SceneObject](#sceneobject)
- [SceneReferenceError](#scenereferenceerror)
- [SceneResult](#sceneresult)
- [TextObject](#textobject)
- [VectorClip](#vectorclip)
- [VisualNode](#visualnode)
- [compile_scene](#compile_scene)

## Lifetime

An absolute half-open seconds interval with 0 <= start < end.

Parent lifetimes further restrict child visibility without changing local
animation clocks.

[Source](../../kara_templater/scene.py#L30)

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

[Source](../../kara_templater/scene.py#L370)

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

[Source](../../kara_templater/scene.py#L279)

```python
ObjectGroup(
    *,
    id: str,
    lifetime: Lifetime,
    state: VisualState = VisualState(position=Vec2(x=0, y=0), scale=Vec2(x=1, y=1), rotation=0, skew=Vec2(x=0, y=0), opacity=1, fill=Color(red=255, green=255, blue=255), outline=Color(red=0, green=0, blue=0), border=0, blur=0, shadow=Vec2(x=0, y=0)),
    animations: tuple[AnimationClip, ...] = (),
    layer: int = 0,
    origin: EventOrigin | None = None,
    clip: RectangleClip | VectorClip | None = None,
    material: PaintField | None = None,
    reference: StateReference | None = None,
    children: tuple[SceneObject, ...],
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `id` | `str` | `required` |
| `lifetime` | `Lifetime` | `required` |
| `state` | `VisualState` | `VisualState(position=Vec2(x=0, y=0), scale=Vec2(x=1, y=1), rotation=0, skew=Vec2(x=0, y=0), opacity=1, fill=Color(red=255, green=255, blue=255), outline=Color(red=0, green=0, blue=0), border=0, blur=0, shadow=Vec2(x=0, y=0))` |
| `animations` | `tuple[AnimationClip, ...]` | `()` |
| `layer` | `int` | `0` |
| `origin` | `EventOrigin \| None` | `None` |
| `clip` | `RectangleClip \| VectorClip \| None` | `None` |
| `material` | `PaintField \| None` | `None` |
| `reference` | `StateReference \| None` | `None` |
| `children` | `tuple[SceneObject, ...]` | `required` |

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

## ObjectReport

Per-object output strategy, event count, source origin, sample interval, and observed geometry/band costs.

Optional metrics apply only to relevant strategies.

[Source](../../kara_templater/scene_output.py#L95)

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

## PathObject

A visual VectorPath drawing with state, lifetime, and optional geometry deformation.

Coordinates are local to its local origin and parent transforms.

[Source](../../kara_templater/scene.py#L246)

```python
PathObject(
    *,
    id: str,
    lifetime: Lifetime,
    state: VisualState = VisualState(position=Vec2(x=0, y=0), scale=Vec2(x=1, y=1), rotation=0, skew=Vec2(x=0, y=0), opacity=1, fill=Color(red=255, green=255, blue=255), outline=Color(red=0, green=0, blue=0), border=0, blur=0, shadow=Vec2(x=0, y=0)),
    animations: tuple[AnimationClip, ...] = (),
    layer: int = 0,
    origin: EventOrigin | None = None,
    clip: RectangleClip | VectorClip | None = None,
    material: PaintField | None = None,
    reference: StateReference | None = None,
    path: VectorPath,
    deform: GeometryAnimation | None = None,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `id` | `str` | `required` |
| `lifetime` | `Lifetime` | `required` |
| `state` | `VisualState` | `VisualState(position=Vec2(x=0, y=0), scale=Vec2(x=1, y=1), rotation=0, skew=Vec2(x=0, y=0), opacity=1, fill=Color(red=255, green=255, blue=255), outline=Color(red=0, green=0, blue=0), border=0, blur=0, shadow=Vec2(x=0, y=0))` |
| `animations` | `tuple[AnimationClip, ...]` | `()` |
| `layer` | `int` | `0` |
| `origin` | `EventOrigin \| None` | `None` |
| `clip` | `RectangleClip \| VectorClip \| None` | `None` |
| `material` | `PaintField \| None` | `None` |
| `reference` | `StateReference \| None` | `None` |
| `path` | `VectorPath` | `required` |
| `deform` | `GeometryAnimation \| None` | `None` |

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

## RectangleClip

A positive-area normal or inverse rectangle in screen or object-local space.

Optional deformation evaluates local seconds and can produce an empty mask.

[Source](../../kara_templater/scene.py#L77)

```python
RectangleClip(
    left: float,
    top: float,
    right: float,
    bottom: float,
    inverse: bool = False,
    space: Literal['screen', 'local'] = 'screen',
    deform: RectangleFunction | None = None,
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
| `deform` | `RectangleFunction \| None` | `None` |

## RectangleFunction

Pure local-seconds rectangle bounds; None denotes an empty mask.

[Source](../../kara_templater/scene.py#L51)

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

## Scene

A Document-backed composition of visual objects and already-lowered NativeEvents.

add and source replacement configure generation; compile returns a new standard
ASS Document and reports.

[Source](../../kara_templater/scene.py#L388)

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

```python
Scene.compile(
    *,
    budget: SceneBudget | None = None,
    native_tweens: bool = False,
) -> SceneResult
```

### Scene.evaluator

Construct a seekable world-space evaluator for this scene hierarchy and its references.

```python
Scene.evaluator() -> SceneEvaluator
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

[Source](../../kara_templater/scene_output.py#L61)

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

## SceneCompileError

An invalid scene or exceeded compilation limit with object_id and optional source origin.

Callback causes remain available for diagnosis.

[Source](../../kara_templater/scene_output.py#L47)

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

[Source](../../kara_templater/scene_output.py#L112)

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
budgets.

[Source](../../kara_templater/scene.py#L212)

```python
TextObject(
    *,
    id: str,
    lifetime: Lifetime,
    state: VisualState = VisualState(position=Vec2(x=0, y=0), scale=Vec2(x=1, y=1), rotation=0, skew=Vec2(x=0, y=0), opacity=1, fill=Color(red=255, green=255, blue=255), outline=Color(red=0, green=0, blue=0), border=0, blur=0, shadow=Vec2(x=0, y=0)),
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
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `id` | `str` | `required` |
| `lifetime` | `Lifetime` | `required` |
| `state` | `VisualState` | `VisualState(position=Vec2(x=0, y=0), scale=Vec2(x=1, y=1), rotation=0, skew=Vec2(x=0, y=0), opacity=1, fill=Color(red=255, green=255, blue=255), outline=Color(red=0, green=0, blue=0), border=0, blur=0, shadow=Vec2(x=0, y=0))` |
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

## VectorClip

A filled mask; deform uses object-local seconds. None is an empty region.

Empty normal masks hide the object; empty inverse masks reveal it entirely.
Local coordinates are relative to the object's alignment anchor.

[Source](../../kara_templater/scene.py#L100)

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

Local evaluation is distinct from world-space SceneEvaluator queries.

[Source](../../kara_templater/scene.py#L122)

```python
VisualNode(
    *,
    id: str,
    lifetime: Lifetime,
    state: VisualState = VisualState(position=Vec2(x=0, y=0), scale=Vec2(x=1, y=1), rotation=0, skew=Vec2(x=0, y=0), opacity=1, fill=Color(red=255, green=255, blue=255), outline=Color(red=0, green=0, blue=0), border=0, blur=0, shadow=Vec2(x=0, y=0)),
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
| `animations` | `tuple[AnimationClip, ...]` | `()` |
| `layer` | `int` | `0` |
| `origin` | `EventOrigin \| None` | `None` |
| `clip` | `RectangleClip \| VectorClip \| None` | `None` |
| `material` | `PaintField \| None` | `None` |
| `reference` | `StateReference \| None` | `None` |

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

## compile_scene

Return a new Document. Source records and caller-owned nodes never mutate.

[Source](../../kara_templater/scene_output.py#L759)

```python
compile_scene(
    scene: Scene,
    *,
    budget: SceneBudget | None = None,
    native_tweens: bool = False,
) -> SceneResult
```
