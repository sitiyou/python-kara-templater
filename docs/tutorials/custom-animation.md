# Write a reusable custom animation

Write a Python function that sends a row of sparks across the scene. The script
uses the installed library and writes `sparks.hook` in the current directory.
[Install the library](../getting-started.md#install-from-the-checkout)

## Define the motion and object

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

`spark` is an ordinary factory. Each call constructs an independently editable
object with a unique identity, a world position, and an absolute lifetime.
The clip starts at the object's birth and runs for two seconds.

`drift` receives the incoming state and normalized clip progress. It calculates
the new state without remembering previous calls. Declaring its written channels
allows the engine to detect animation conflicts and preserve unrelated changes.

## Customize the result

Change the circle to another VectorPath, alter the curve in `drift`, or change
the number and birth times of the objects. Keep the channel declaration aligned
with the fields the callback writes. Use explicit breakpoints for discontinuities.

For randomized particles, switch to [emit_particles](../guides/particles.md) and
named random channels. For a lyric sweep, bind [Document text](../guides/text-and-cues.md)
or prepare [Tracks](../guides/tracks.md), then add the same objects to that Scene.

The hook runs the GLSL body at the current clip progress. The Python evaluator supplies state at clip boundaries.
