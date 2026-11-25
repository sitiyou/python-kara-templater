# Write a custom animation

Create a reusable Python animation that sends a row of spinning sparks across a Hook scene. Use this approach when built-in animations do not express the curve you want and you need decorations with their own lifetimes.

## Animate a row of sparks

This complete script defines a sine-wave drift with rotation and fade-out, attaches it to four staggered pink circles, and writes `sparks.hook` in the current directory.

```python
from dataclasses import replace
from math import sin, tau

from kara_templater import (
    PINK,
    AnimationClip,
    Document,
    Lifetime,
    PathObject,
    Scene,
    ShaderMotion,
    Vec2,
    VectorPath,
    VisualState,
)


def drift(state: VisualState, progress: float) -> VisualState:
    return replace(
        state,
        position=state.position + Vec2(300 * progress, 30 * sin(tau * progress)),
        rotation=360 * progress,
        opacity=1 - progress,
    )


def spark(identity: str, position: Vec2, birth: float) -> PathObject:
    return PathObject(
        id=identity,
        path=VectorPath.circle(8),
        lifetime=Lifetime(birth, birth + 2),
        state=VisualState(position=position, fill=PINK),
        animations=(AnimationClip(
            0, 2,
            ShaderMotion(drift, frozenset(("position", "rotation", "opacity")),
                         "pos += vec2(300.*p,30.*sin(6.28318531*p)); angle=360.*p; alpha=1.-p;"),
        ),),
    )


scene = Scene(Document.create(width=640, height=360)).add(
    *(spark(f"spark:{i}", Vec2(100, 100 + i * 35), i * 0.1) for i in range(4))
)
scene.export("sparks.hook", fps=60)
```

## How the motion and factory work

`spark` is an ordinary Python factory function. Each call builds an independent `PathObject` with a unique `id`, a starting position, and an absolute `Lifetime`. The `AnimationClip` starts at local time `0` (the spark's birth) and runs for `2` seconds.

`drift` is a pure function of `(state, progress)` where `progress` runs from `0` to `1`. It computes the new `VisualState` directly from the incoming state without storing previous frames, so the scene can be evaluated at any timestamp in any order.

`ShaderMotion` connects that pure Python function to Hook playback:

- **Declared `channels`** (`position`, `rotation`, `opacity`) tell the engine which fields this clip modifies so it can catch conflicting animations and preserve untouched channels.
- **The GLSL body** runs on the GPU at each frame's normalized clip progress `p`, updating local shader variables (`pos`, `angle`, `alpha`).
- **The Python callback** (`drift`) supplies exact state at clip boundaries and indexes object bounds on the output frame grid during Hook export.

> [!IMPORTANT]
> Keep the Python function, the declared `channels` set, and the GLSL body aligned. If the Python callback writes a channel that is missing from `channels`, conflict detection will miss it; if the Python curve and GLSL body diverge, clipping bounds and rendered positions will disagree.

## Customize the animation

You can reuse the same pattern while changing any part independently:

- **Shape**: replace `VectorPath.circle(8)` with `VectorPath.polygon(...)` or any custom `VectorPath`.
- **Path and easing**: change the wave amplitude, travel distance, or spin in both `drift` and the GLSL string.
- **Schedule**: change the loop count, spacing, or `birth` offset to stagger more sparks.
- **Discontinuities**: pass `breakpoints=(...)` to `AnimationClip` if your curve jumps abruptly at a specific local second.

When you need many randomized shapes, switch to `emit_particles` so each particle gets deterministic named random channels. To combine custom animated decorations with timed lyrics, build your lyrics with `Track` and add your custom objects to the returned `Scene`.

## Next steps

- [Animation and timing](../guides/animation.md) for `Transform`, `StateFunction`, `ShaderMotion`, and `Timeline`.
- [Particles, copies and echoes](../guides/particles.md) for `emit_particles` and `LyricParticles`.
- [Play and render a Hook](../output/hook.md) to preview `sparks.hook` in mpv or FFmpeg.
- [API reference: Animation and timing](../reference/animation.md) for all `ShaderMotion` GLSL variables and fields.
