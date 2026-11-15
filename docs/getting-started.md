# Getting started

kara-templater is a Python library for custom effects that compile to standard
ASS subtitles. You create a Document, add objects to a Scene, animate them, and
save the compiled Document. A video renderer is not required to generate ASS.

## Install the library

Python 3.12 or later is required. These docs describe the current checkout;
an older published release may expose a different API. Install a wheel built
from this version, or install the checkout after following the platform-specific
[build prerequisites](contributing/setup.md):

```sh
python -m venv .venv
```

Activate the environment before installing: use `source .venv/bin/activate` on
Linux or `.venv\Scripts\Activate.ps1` in Windows PowerShell. Then, from the
checkout root:

```sh
python -m pip install .
```

After installation you can move to any working directory for the script below.
To install a matching wheel instead, use `python -m pip install path/to/package.whl`.
See [development setup](contributing/setup.md) for wheel builds and Linux runtime
library requirements.

## Write your first effect

Save this complete script as `first_effect.py`. It uses only the installed
library; no repository example modules or input subtitle file are needed.

```python
from kara_templater import (
    CYAN,
    AnimationClip,
    Document,
    Lifetime,
    Scene,
    StatePatch,
    TextObject,
    Tween,
    Vec2,
    VisualState,
)

document = Document.create(width=640, height=360)
caption = TextObject(
    id="caption",
    text="Hello, ASS!",
    font="DejaVu Sans",
    font_size=48,
    alignment=5,
    lifetime=Lifetime(0, 3),
    state=VisualState(position=Vec2(320, 210), fill=CYAN, opacity=0),
    animations=(
        AnimationClip(0, 0.6, Tween(StatePatch(position=Vec2(320, 180), opacity=1))),
        AnimationClip(2.5, 0.5, Tween(StatePatch(opacity=0))),
    ),
)
result = Scene(document).add(caption).compile()
result.document.save("first-effect.ass")
print(f"{result.event_count} events, {result.byte_count} bytes")
```

Run it with:

```sh
python first_effect.py
```

The result is a three-second caption that rises while fading in, then fades out.
Load `first-effect.ass` as a subtitle track in an ASS-capable player. Use a video
lasting at least three seconds and ensure the requested font is installed or
available to the player. A fallback font can change the result's appearance.

## Change the effect

- Change `text`, `fill`, `font_size`, or the positions to change the caption.
- Scene lifetimes and animation durations are in **seconds**. Positions use
  script pixels in the Document's 640 by 360 coordinate system.
- An AnimationClip starts relative to the object's birth. The final animation
  value is held until another animation writes the same channel.
- `compile()` enforces event, byte, activity, and geometry budgets. Inspect the
  result before increasing a budget for a complex effect.
- Existing subtitle files enter through `Document.load("input.ass")`. Loading
  a file does not execute embedded Python templates.

Repository examples are a separate workflow: their `python -m examples...`
commands require a source checkout. They are not installed with the wheel.

Continue with the [custom animation tutorial](tutorials/custom-animation.md), or
browse the [effect gallery](examples/README.md).
