# Particles and references

Deterministic emissions, delayed copies, and pure world-space dependencies. Time values use seconds. See [particles](../guides/particles.md).

[All public symbols](README.md#symbol-index)

## Contents

- [Emission](#emission)
- [FollowObject](#followobject)
- [LyricParticles](#lyricparticles)
- [ParticleContext](#particlecontext)
- [ParticleFactory](#particlefactory)
- [Petal](#petal)
- [ReferenceFunction](#referencefunction)
- [Ribbon](#ribbon)
- [Sparkle](#sparkle)
- [StateLookup](#statelookup)
- [StateReference](#statereference)
- [echoes](#echoes)
- [emit_particles](#emit_particles)
- [split_path](#split_path)

## Emission

A stable particle emission ID and nonnegative absolute birth time in seconds.

Reordering a schedule does not change keyed random values for an existing ID.

[Source](../../kara_templater/particles.py#L30)

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

## LyricParticles

Emit particles at the timing front or throughout the measured lyric line.

placement="front" uses each timing segment. placement="line" scatters
particles across the body bounds from the original preview start through the
last positive timing end, including base text and pauses. Its rate is per
whole line, not per character or segment. Empty/zero-only lines emit nothing.
Copy delays shift both schedules; later visual tails never extend emission.
Line placement uses stable named random channels and captures a fixed point.

color overrides the emission tint. Catalog or Track ink supplies the default;
without one the emitter reads the source run. A factory color overrides it.
rate is particles per second per timing segment in front mode; duration comes from the
particle factory. Repeated segments restart the front. Zero-length segments
emit nothing. Particle births are rounded to the ASS 10 ms grid; source
timing clocks are unchanged. Position is captured in line-local layout coordinates at birth;
line transforms apply to particles, independent character motion does not
retarget already emitted particles. Use a custom factory for different paths,
shapes, animation and lifetimes through the existing ParticleContext protocol.

[Source](../../kara_templater/lyric_particles.py#L156)

```python
LyricParticles(
    *,
    factory: ParticleFactory = Sparkle(color=None, size=3, duration=0.45, travel=Vec2(x=12, y=-24)),
    rate: float = 12,
    seed: int = 0,
    id: str = 'particles',
    max_particles: int = 256,
    placement: Literal['front', 'line'] = 'front',
    color: Color | None = None,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `factory` | `ParticleFactory` | `Sparkle(color=None, size=3, duration=0.45, travel=Vec2(x=12, y=-24))` |
| `rate` | `float` | `12` |
| `seed` | `int` | `0` |
| `id` | `str` | `'particles'` |
| `max_particles` | `int` | `256` |
| `placement` | `Literal['front', 'line']` | `'front'` |
| `color` | `Color \| None` | `None` |

### LyricParticles.__call__

Preflight all emissions, then construct visuals and reserve their tails.

```python
LyricParticles.__call__(
    line: LyricLine,
) -> LyricLine
```

## ParticleContext

Particle factory input with birth, seed, source position, optional origin, and named random channels.

position_at samples an emitter explicitly; it does not imply continuous
following. color is the optional captured lyric ink for a particle factory.

[Source](../../kara_templater/particles.py#L46)

```python
ParticleContext(
    id: str,
    birth: float,
    seed: int,
    position: Vec2,
    origin: EventOrigin | None,
    emitter: Callable[[float], Vec2] | None = None,
    color: Color | None = None,
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
| `color` | `Color \| None` | `None` |

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

[Source](../../kara_templater/particles.py#L87)

### ParticleFactory.__call__

Create one Scene object or group preserving the context ID and birth time.

```python
ParticleFactory.__call__(
    context: ParticleContext,
    /,
) -> SceneObject
```

## Petal

A seeded falling petal with curved drift, rotation and projected flutter.

size/fall are script pixels, duration is seconds. Unlike Sparkle this uses
a custom Transform for flutter and requires hook export.

[Source](../../kara_templater/lyric_particles.py#L65)

```python
Petal(
    *,
    color: Color | None = None,
    size: float = 4,
    duration: float = 0.9,
    fall: float = 40,
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `color` | `Color \| None` | `None` |
| `size` | `float` | `4` |
| `duration` | `float` | `0.9` |
| `fall` | `float` | `40` |

### Petal.__call__

Build an ordinary path object with deterministic custom motion.

```python
Petal.__call__(
    context: ParticleContext,
) -> PathObject
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

## Ribbon

A curved luminous strand whose tail follows its head along one path.

duration is head travel time and lag is tail delay in seconds. width, travel
and bend use local script pixels. Keyed variation changes travel/bend once
at birth; geometry then uses the same TrailPath available to custom authors.
ASS export does not support changing path geometry.

[Source](../../kara_templater/lyric_particles.py#L116)

```python
Ribbon(
    *,
    color: Color | None = None,
    width: float = 1.5,
    duration: float = 0.55,
    lag: float = 0.18,
    travel: Vec2 = Vec2(x=52, y=-18),
    bend: Vec2 = Vec2(x=16, y=-46),
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `color` | `Color \| None` | `None` |
| `width` | `float` | `1.5` |
| `duration` | `float` | `0.55` |
| `lag` | `float` | `0.18` |
| `travel` | `Vec2` | `Vec2(x=52, y=-18)` |
| `bend` | `Vec2` | `Vec2(x=16, y=-46)` |

### Ribbon.__call__

Create one seeded path trail with an independent head/tail clock.

```python
Ribbon.__call__(
    context: ParticleContext,
) -> PathObject
```

## Sparkle

A small four-point sparkle drifting upward while fading.

A ParticleFactory usable with LyricParticles or emit_particles. size and
travel are script pixels, duration is seconds; variation uses keyed seed
channels. The ordinary linear Tween can compile to one ASS event per spark.

[Source](../../kara_templater/lyric_particles.py#L25)

```python
Sparkle(
    *,
    color: Color | None = None,
    size: float = 3,
    duration: float = 0.45,
    travel: Vec2 = Vec2(x=12, y=-24),
)
```

### Fields

| Name | Type | Default |
| --- | --- | --- |
| `color` | `Color \| None` | `None` |
| `size` | `float` | `3` |
| `duration` | `float` | `0.45` |
| `travel` | `Vec2` | `Vec2(x=12, y=-24)` |

### Sparkle.__call__

Create one seeded sparkle from the captured emitter position.

```python
Sparkle.__call__(
    context: ParticleContext,
) -> PathObject
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

[Source](../../kara_templater/particles.py#L163)

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

[Source](../../kara_templater/particles.py#L108)

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

Cut static filled geometry into local cells, retaining object origin.

Give both grid dimensions or supply convex polygons in source-local
coordinates. Custom cells may overlap or leave gaps. Empty intersections
are skipped and custom piece IDs retain the original cell index.

Pieces move with their own geometry, not fixed screen-space clips. Appearance
is preserved, so borders will also outline newly cut edges. Separate raster
edges can show seams; use the uncut object for the final assembled hold.

[Source](../../kara_templater/particles.py#L293)

```python
split_path(
    source: PathObject,
    *,
    columns: int | None = None,
    rows: int | None = None,
    cells: Sequence[Sequence[Vec2]] | None = None,
    tolerance: float = 0.25,
    max_fragments: int = 256,
    max_points: int = 4096,
) -> tuple[PathObject, ...]
```
