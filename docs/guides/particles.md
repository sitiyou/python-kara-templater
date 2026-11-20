# Particles, copies, echoes, and following

Particle effects create ordinary Scene objects. An Emission gives a stable ID
and birth time; emit_particles calls a ParticleFactory with ParticleContext.
The factory chooses geometry, lifetime, appearance, and animation and returns
an object or group. See the sakura example for a complete editable petal factory.

The built-in lyric particle factories use an explicit factory color first,
then the emitter ink. `LyricParticles` takes that ink from its `color`, the
catalog or track sung role, or the source run. A standalone emitter with
no lyric context uses the catalog accent. Custom factories can read
`ParticleContext.color` at birth.

## Singing-onset echoes

`LyricEcho` is a built-in lyric factory. It emits full-glyph copies at each
positive singing interval, including repeated intervals, and reserves their
display time automatically. Combine built-in and custom factories in order:

```python
from kara_templater import (
    RED,
    LyricEcho,
    LyricHighlights,
    StatePatch,
    Track,
    Vec2,
)

track = Track(
    id="main",
    effects=(
        LyricHighlights.from_singing(StatePatch(fill=RED)),
        LyricEcho(
            count=3,
            offset=Vec2(0, -8),
            spacing=0.06,
            duration=0.45,
            paint=StatePatch(fill=RED),
        ),
    ),
)
```

Each successive copy is farther from the original and starts `spacing` seconds
later. `opacity` multiplies original opacity and `decay` attenuates successive
copies. Copies fade linearly and retain parent line/syllable transforms. With
eligible static parents and `native_tweens=True`, each copy uses one ASS event.

This onset effect uses the prepared glyph's static appearance, removes its sweep
mask/material and existing animation, and shows the complete glyph. It does not
sample the glyph's motion history; use `echoes` below for historical copies.
Ordinary lyric rules still select the original glyph; `target="ruby"` selects
readings instead. `max_copies` limits expansion before copying. Coverage-mode
composition is not supported; source singing and decoded text remain unchanged.

`lyric_effects` also accepts ordinary custom functions from LyricLine to LyricLine.
They run once during preparation and must preserve the line identity. Generated
visuals use the same Scene nodes, animation evaluation and compilation as any
other effect.

The complete [lyric echo example](../../examples/lyric_echo.py) includes short
and held notes and can be compiled directly to ASS.

## Reproducible variation

`LyricParticles()` provides a measured singing-front emitter with `Sparkle()` as
its default particle factory. Put it beside the highlighter in `Track.effects`,
just as with `LyricEcho`. Use `factory=Petal()` for curved,
falling, fluttering petals, or pass your own `ParticleFactory` to control shape,
animation and lifetime. The [runnable lyric particle example](../../examples/lyric_particles.py)
shows both built-ins on the same short/held-note fixture.

`rate` is particles per second per singing segment. Repeats restart the measured
front; zero-length and whitespace units emit nothing. Births are rounded to the
ASS 10 ms grid, without changing source singing clocks. Positions use undecorated
body layout, so glow does not slow down the front. Particles capture the layout
position at birth and inherit line transforms; independent glyph animations do
not retarget the emitted particles. `max_particles` is checked across the line
before invoking any factory. Factories can reserve longer tails through their
returned lifetimes; the layout automatically includes those intervals.

Use `LyricParticles(factory=Petal(), placement="line")` for petals around the
whole lyric, including unsung text. One schedule runs from the line's original
preview start through its last positive singing end, including pauses; `rate`
is per line. Positions are seeded uniformly inside measured body bounds. Copies
shift the schedule, and other effects' reserved tails do not extend emission.
A custom factory receives the same `ParticleContext`; `position_at` stays fixed
for this placement. Source timing and independent track layout remain unchanged.

`LyricParticles(factory=Ribbon(), rate=6)` emits luminous curved strands.
`Ribbon` is a small built-in factory using `TrailPath`; `travel`, `bend`, `width`,
head `duration` and tail `lag` are its appearance/motion controls. For different
paths, use a custom factory returning a PathObject with TrailPath deformation,
as shown in the [geometry guide](geometry.md#path-trails). A trail consists of
connected stroke geometry, not a row of independent dots.

Sparkles use one native move with a fading transform when native lowering is
enabled and the surrounding scene permits it. Petal flutter is a sampled custom
`Transform`, so it costs more events. Both use the existing keyed random channels
and ordinary Scene objects; neither has a separate playback engine.

A simple custom particle does not need its own animation class:

```python
from kara_templater import (
    Lifetime, LyricParticles, ParticleContext, PathObject, Transform,
    Vec2, VectorPath, VisualState,
)

def dot(context: ParticleContext) -> PathObject:
    return PathObject(
        id=context.id,
        lifetime=Lifetime(context.birth, context.birth + 0.4),
        path=VectorPath.rectangle(2, 2),
        state=VisualState(position=context.position),
    ).animate(
        Transform(offset=lambda p: Vec2(0, -20 * p), opacity=lambda p: 1 - p),
        duration=0.4,
    )

particles = LyricParticles(factory=dot)
```

Put `particles` in `Track.effects`, or call it on a LyricLine in a custom effect. Keep the context ID and
birth time; choose any supported path, color, lifetime or common animation.

Use a fixed seed and named channels such as `context.uniform("size", low, high)`.
Random values are keyed by seed, emission ID, and channel. Adding a new random
property does not advance an unrelated property's random stream. Avoid global
random draws inside animation callbacks: evaluation may seek, repeat, or visit
objects in a different order.

Changing a seed deliberately changes variation. Preserve emission IDs when you
want stable particles across a configuration edit. Give the factory an explicit
particle lifetime instead of tying visibility to a source lyric's duration.

## Three different time relationships

| Relationship | Interface | Behavior |
| --- | --- | --- |
| Capture at birth | Emission/factory and emission-source lookup | Read the source once at birth; particle then moves independently |
| Follow continuously | FollowObject or ReferenceFunction | Evaluate the referenced object's world state at the requested time |
| Reuse earlier motion | echoes or delayed copies/references | Draw a delayed historical appearance with explicit spacing/opacity |

Use Scene.evaluator() for world-space queries across parent groups. References
receive absolute Scene seconds, and their lookup function uses that same clock.
Material and geometry callbacks instead use object-local seconds.
References
declare their dependencies; unknown IDs or dependency cycles produce contextual
errors. Keep callback output deterministic for arbitrary seeks.

`copy` and echoes preserve local clocks and make distinct identities. Group
copies remap references within the copied hierarchy. External material and
coverage maps remain keyed by ID and need explicit remapping.

Particle count, lifetime overlap, geometry detail, color bands, and echoes all
contribute to compilation and playback cost. Plan emission density with
SceneBudget.max_active and event/byte limits; a visually small petal can still
have expensive geometry or glow. Read [compilation](compilation.md) before
increasing a dense effect's limits.
