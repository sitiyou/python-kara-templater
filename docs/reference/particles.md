# Particles and references

Deterministic emissions, delayed copies, and pure world-space dependencies. Time values use seconds. See [particles](../guides/particles.md).

[All public symbols](README.md#symbol-index)

## Contents

- [Emission](#emission)
- [FollowObject](#followobject)
- [ParticleContext](#particlecontext)
- [ParticleFactory](#particlefactory)
- [ReferenceFunction](#referencefunction)
- [StateLookup](#statelookup)
- [StateReference](#statereference)
- [echoes](#echoes)
- [emit_particles](#emit_particles)
- [split_path](#split_path)

## Emission

A stable particle emission ID and nonnegative absolute birth time in seconds.

Reordering a schedule does not change keyed random values for an existing ID.

[Source](../../kara_templater/particles.py#L29)

```python
Emission(
    id: str,
    birth: float,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `id` | `str` | `required` |
| `birth` | `float` | `required` |

## FollowObject

Replace selected world channels with a target's state at time-delay.

offset is a screen-space position offset, independent of target rotation.
The target state clamps to its own lifetime at the evaluator boundary.

[Source](../../kara_templater/object_references.py#L58)

```python
FollowObject(
    target: str,
    offset: Vec2 = Vec2(x=0, y=0),
    delay: float = 0,
    opacity_factor: float = 1,
    channels: frozenset[Channel] = frozenset({'position'}),
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `target` | `str` | `required` |
| `offset` | `Vec2` | `Vec2(x=0, y=0)` |
| `delay` | `float` | `0` |
| `opacity_factor` | `float` | `1` |
| `channels` | `frozenset[Channel]` | `frozenset({'position'})` |

### FollowObject.breakpoints

Declared time boundaries that must be considered while sampling this reference.

Type: `tuple[float, ...]`.

### FollowObject.dependencies

The source object IDs required for world-state evaluation.

Type: `tuple[str, ...]`.

### FollowObject.retarget

Remap dependency IDs and time shifts when copying a referenced hierarchy.

```python
FollowObject.retarget(
    names: Mapping[str, str],
    time_shift: float = 0,
) -> FollowObject
```

### FollowObject.sample

Resolve the followed object through the supplied world-state lookup and apply the requested relationship.

```python
FollowObject.sample(
    base: VisualState,
    time: float,
    lookup: StateLookup,
) -> VisualState
```

### FollowObject.shifted

Return a reference with its time relationship shifted by a seconds delay.

```python
FollowObject.shifted(
    seconds: float,
) -> FollowObject
```

### FollowObject.translated

Return a reference with its coordinate offset translated for object copying.

```python
FollowObject.translated(
    offset: Vec2,
) -> FollowObject
```

## ParticleContext

Particle factory input with birth, seed, source position, optional origin, and named random channels.

position_at samples an emitter explicitly; it does not imply continuous
following.

[Source](../../kara_templater/particles.py#L45)

```python
ParticleContext(
    id: str,
    birth: float,
    seed: int,
    position: Vec2,
    origin: EventOrigin | None,
    emitter: Callable[[float], Vec2] | None = None,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `id` | `str` | `required` |
| `birth` | `float` | `required` |
| `seed` | `int` | `required` |
| `position` | `Vec2` | `required` |
| `origin` | `EventOrigin \| None` | `required` |
| `emitter` | `Callable[[float], Vec2] \| None` | `None` |

### ParticleContext.choose

Select deterministically from values using a named random channel.

```python
ParticleContext.choose(
    key: str,
    values: tuple[T, ...],
) -> T
```

### ParticleContext.position_at

Continuously follow the emitter; position itself is its birth capture.

```python
ParticleContext.position_at(
    age: float,
) -> Vec2
```

### ParticleContext.uniform

Stable keyed random value, independent of access and generation order.

```python
ParticleContext.uniform(
    key: str,
    minimum: float = 0,
    maximum: float = 1,
) -> float
```

## ParticleFactory

A callable producing a normal Scene object or group from ParticleContext.

The factory controls its own geometry, animation, and lifetime.

[Source](../../kara_templater/particles.py#L85)

### ParticleFactory.__call__

Create one Scene object or group preserving the context ID and birth time.

```python
ParticleFactory.__call__(
    context: ParticleContext,
    /,
) -> SceneObject
```

## ReferenceFunction

A pure world-state callback with explicit dependency IDs, written channels, and second-based breakpoints.

Retargeting and clock translation support copied groups.

[Source](../../kara_templater/object_references.py#L127)

```python
ReferenceFunction(
    function: Callable[[VisualState, float, StateLookup], VisualState],
    dependencies: tuple[str, ...],
    channels: frozenset[Channel],
    breakpoints: tuple[float, ...] = (),
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `function` | `Callable[[VisualState, float, StateLookup], VisualState]` | `required` |
| `dependencies` | `tuple[str, ...]` | `required` |
| `channels` | `frozenset[Channel]` | `required` |
| `breakpoints` | `tuple[float, ...]` | `()` |

### ReferenceFunction.retarget

Remap dependency identities and delay when copying a group.

```python
ReferenceFunction.retarget(
    names: Mapping[str, str],
    time_shift: float = 0,
) -> ReferenceFunction
```

### ReferenceFunction.sample

Evaluate the pure reference callback with the incoming state, seconds time, and world-state lookup.

```python
ReferenceFunction.sample(
    base: VisualState,
    time: float,
    lookup: StateLookup,
) -> VisualState
```

### ReferenceFunction.shifted

Return a reference adjusted for a seconds clock shift.

```python
ReferenceFunction.shifted(
    seconds: float,
) -> ReferenceFunction
```

### ReferenceFunction.translated

Return a reference adjusted for a spatial translation.

```python
ReferenceFunction.translated(
    offset: Vec2,
) -> ReferenceFunction
```

## StateLookup

Public type alias:

```python
type StateLookup = Callable[[str, float], VisualState]
```

## StateReference

Protocol for seekable state relationships evaluated through a world-state lookup.

Declare dependencies and channels so references can be ordered and checked for
cycles.

[Source](../../kara_templater/object_references.py#L15)

### StateReference.breakpoints

Declared seconds boundaries used when sampling dependent objects.

Type: `tuple[float, ...]`.

### StateReference.channels

The state channels this reference may change.

Type: `frozenset[Channel]`.

### StateReference.dependencies

Object identities that the world-state evaluator must resolve first.

Type: `tuple[str, ...]`.

### StateReference.retarget

Remap dependencies and delay for a copied object hierarchy.

```python
StateReference.retarget(
    names: Mapping[str, str],
    time_shift: float = 0,
) -> StateReference
```

### StateReference.sample

Evaluate a pure state relationship using the supplied world-state lookup.

```python
StateReference.sample(
    base: VisualState,
    time: float,
    lookup: StateLookup,
) -> VisualState
```

### StateReference.shifted

Return a reference with a seconds clock shift for delayed copying.

```python
StateReference.shifted(
    seconds: float,
) -> StateReference
```

### StateReference.translated

Return a reference adjusted for a spatial translation.

```python
StateReference.translated(
    offset: Vec2,
) -> StateReference
```

## echoes

Historical copies of complete animation/geometry, each with independent life.

Group copies delay their descendants and parent transforms together. Opacity
remains the library's per-child inherited opacity, not offscreen compositing.

[Source](../../kara_templater/particles.py#L161)

```python
echoes(
    source: T,
    *,
    count: int = 4,
    spacing: float = 0.06,
    opacity: float = 0.4,
    decay: float = 0.7,
    layer_step: int = -1,
    max_objects: int = 1000,
) -> tuple[T, ...]
```

## emit_particles

Validate the finite schedule before calling factories or the emitter.

A stable emission id owns its random stream. Reordering or adding unrelated
emissions doesn't change existing particles. Each factory controls geometry,
state, animation and lifespan through the same normal scene object interface.

[Source](../../kara_templater/particles.py#L106)

```python
emit_particles(
    emissions: Iterable[Emission],
    factory: ParticleFactory,
    *,
    id: str = 'particles',
    seed: int = 0,
    emitter: Callable[[float], Vec2] | None = None,
    origin: EventOrigin | None = None,
    max_particles: int = 1000,
) -> tuple[SceneObject, ...]
```

## split_path

Cut static filled geometry into local grid cells, retaining object origin.

Pieces move with their own geometry, not fixed screen-space clips. Appearance
is preserved, so borders will also outline newly cut edges. Separate raster
edges can show seams; use the uncut object for the final assembled hold.

[Source](../../kara_templater/particles.py#L291)

```python
split_path(
    source: PathObject,
    *,
    columns: int,
    rows: int,
    tolerance: float = 0.25,
    max_fragments: int = 256,
    max_points: int = 4096,
) -> tuple[PathObject, ...]
```
