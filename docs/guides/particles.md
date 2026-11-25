# Particles, copies and echoes

Emit deterministic particles along the karaoke sweep, add onset echoes to lyrics, or link objects with delayed copies and world-space references. Use this guide to add layered motion without manual per-frame loops.

## Emit particles along the lyrics

Add `LyricParticles` to `Track.effects` to emit ordinary scene objects along the timed sweep without writing an emission loop.

```python
from kara_templater import (
    CYAN,
    LyricHighlights,
    LyricParticles,
    Sparkle,
    StatePatch,
    Track,
)

track = Track(
    id="main",
    effects=(
        LyricHighlights.from_timing(StatePatch(fill=CYAN)),
        LyricParticles(factory=Sparkle(size=4), rate=16, seed=42),
    ),
)
```

See [the lyric particles example](../../examples/lyric_particles.py) for a complete runnable script comparing sparkles and petals.

Choose from three built-in particle factories or supply your own:

| Factory | Appearance | Output support |
| --- | --- | --- |
| `Sparkle(color=None, size=3, duration=0.45, travel=Vec2(12, -24))` | Default. Four-point star drifting upward and fading | Hook and ASS |
| `Petal(color=None, size=4, duration=0.9, fall=40)` | Curved falling petal with rotation and flutter | Hook |
| `Ribbon(color=None, width=1.5, duration=0.55, lag=0.18, travel=..., bend=...)` | Curved luminous strand built with `TrailPath` | `SceneEvaluator` (deformed path) |

Particle colour follows a clear fallback chain: an explicit `color` on the factory wins first, then `LyricParticles(color=...)`, then the track or catalog highlight colour, and finally the source text run (or catalog accent if used outside a lyric track). Custom factories read this resolved tint from `context.color`.

Control where and how many particles appear:

- **`placement="front"`** (default): Emits `rate` particles per second along the undecorated body wipe front during each positive timing segment. Repeats restart the front; whitespace and zero-length segments emit nothing.
- **`placement="line"`**: Scatters particles uniformly across the measured body bounds from the line's original preview start through its final positive timing end (including pauses). Here `rate` is per whole line.
- **Layout and budgets**: Particles capture their line-local position at birth and inherit whole-line transforms, while independent glyph animations do not pull already-emitted particles. Layout automatically reserves particle tails, and `max_particles` (default `256`) is checked across the line before any factory runs.

## Write a custom particle factory

A `ParticleFactory` is any callable taking a `ParticleContext` and returning a `TextObject`, `PathObject` or `ObjectGroup`. Keep `context.id` and `context.birth`, and use built-in animations (such as `Slide`, `FadeOut`, `Tween` or `ShaderMotion`) so the emitted particles export to Hook:

```python
from kara_templater import (
    WHITE,
    Lifetime,
    LyricParticles,
    ParticleContext,
    PathObject,
    Slide,
    Vec2,
    VectorPath,
    VisualState,
)


def dot(context: ParticleContext) -> PathObject:
    drift = Vec2(context.uniform("dx", -14, 14), context.uniform("dy", -32, -16))
    return PathObject(
        id=context.id,
        lifetime=Lifetime(context.birth, context.birth + 0.45),
        path=VectorPath.circle(context.uniform("r", 1.5, 3.0)),
        state=VisualState(position=context.position, fill=context.color or WHITE),
    ).animate(Slide(drift, entering=False), duration=0.45)


particles = LyricParticles(factory=dot, rate=14, seed=7)
```

Use named random channels — `context.uniform(key, low, high)` and `context.choose(key, values)` — instead of Python's global `random` module. Each value is keyed by `(seed, emission_id, key)`, so adding a new random property or reordering emissions never disturbs existing particles, and seeking to any frame stays deterministic.

To emit particles outside a lyric track, call `emit_particles(emissions, factory, seed=..., emitter=..., max_particles=1000)` with a sequence of `Emission(id, birth)` values. Supply an explicit particle lifetime rather than tying visibility to a lyric's duration.

## Add onset echoes to lyrics

Add `LyricEcho` to `Track.effects` to spawn offset, fading copies of each character (or ruby reading with `target="ruby"`) at every positive timing onset, including repeated notes:

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
        LyricHighlights.from_timing(StatePatch(fill=RED)),
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

Each copy shifts further by `offset`, starts `spacing` seconds later, multiplies initial opacity by `opacity` (default `0.35`), and attenuates each step by `decay` (default `0.65`). By default copies fade linearly with `FadeOut()`, and you can supply any `StateAnimation` via `animation=`. Set a negative `delay` for approaching echoes before onset (clamped so nothing precedes Scene zero).

`LyricEcho` copies the glyph's prepared static appearance without its sweep mask, material or existing animation, so it shows the complete letter at onset while still inheriting parent line and syllable transforms. Layout reserves the echo tail automatically, and `max_copies` (default `256`) bounds expansion up front. See [the lyric echo example](../../examples/lyric_echo.py) for a complete runnable script.

You can also compose custom `(LyricLine) -> LyricLine` functions in `Track.effects` (or group them with `lyric_effects(...)`); each runs once during preparation and must preserve the line's identity.

## Follow objects and create historical copies

Pick the right linking mechanism based on how one object's timing relates to another:

| Relationship | API | Behaviour |
| --- | --- | --- |
| Capture at birth | `LyricParticles`, `emit_particles` | Reads the emitter position once at birth; the particle then moves independently |
| Follow continuously | `FollowObject`, `ReferenceFunction` | Evaluates the referenced object's world state at `time - delay` |
| Reuse earlier motion | `echoes`, `object.copy(delay=...)` | Draws delayed copies of an object's complete animation and geometry |

### Historical motion echoes

Unlike `LyricEcho` (static copies at note onset), `echoes(source, count=4, spacing=0.06, opacity=0.4, decay=0.7, layer_step=-1, max_objects=1000)` duplicates any `TextObject`, `PathObject` or `ObjectGroup` with its full animation delayed behind the original. Each copy keeps its own local animation clock, and group copies delay descendants and parent transforms together.

### World-space references

Attach `FollowObject(target, offset=Vec2(), delay=0, opacity_factor=1, channels=frozenset({"position"}))` to a node's `reference=` field to track another object's world state continuously (including parent group transforms).

For custom tracking formulas, use `ReferenceFunction(function, dependencies, channels, breakpoints=())`. Both receive absolute Scene seconds and a `StateLookup` function, declare their dependency IDs up front (catching missing IDs and dependency cycles before export), and automatically retarget when an `ObjectGroup` is copied.

> [!TIP]
> Particle count, lifetime overlap, path point count and echo stacks all multiply rendering work. Keep `max_particles`, `max_copies` and `max_objects` tight, and check tile limits in [Play and render a Hook](../output/hook.md) or event limits in [Export standard ASS](../output/ass.md) before raising budgets.

## Next steps

- Try built-in transition and timing particles in [Built-in karaoke effects](karaoke-effects.md).
- Build custom curves and GPU motions for particles in [Animation and timing](animation.md).
- Shape custom particle geometry in [Shapes, clips and masks](geometry.md).
- Check Hook performance and tile budgets in [Play and render a Hook](../output/hook.md).
