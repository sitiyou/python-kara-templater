# kara-templater

A typed Python library for highly customizable karaoke and animation effects,
compiled to **standard ASS subtitles**. Create text, paths, groups, gradients,
particles, and lyric cues using ordinary Python objects and functions.

```python
from kara_templater import (
    CYAN, AnimationClip, Document, Lifetime, Scene, StatePatch,
    TextObject, Tween, Vec2, VisualState,
)

caption = TextObject(
    id="hello",
    text="Hello, ASS!",
    alignment=5,
    lifetime=Lifetime(0, 3),
    state=VisualState(position=Vec2(320, 180), fill=CYAN, opacity=0),
    animations=(AnimationClip(0, 0.5, Tween(StatePatch(opacity=1))),),
)
result = Scene(Document.create(width=640, height=360)).add(caption).compile()
result.document.save("hello.ass")
```

Python 3.12 or later is required. These docs describe the current checkout.
Install a matching wheel or follow the [installation instructions](docs/getting-started.md).

## Learn and create

- [Getting started](docs/getting-started.md): install the library and run a complete standalone script.
- [Effect gallery](docs/examples/README.md): animated previews, runnable source, and customization points.
- [First custom animation](docs/tutorials/custom-animation.md): build a reusable effect with your own function.
- [Guides](docs/README.md): objects, lyrics, timing, geometry, materials, particles, compilation, and troubleshooting.
- [API reference](docs/reference/README.md): all retained public interfaces, grouped by topic.

## Work with existing lyrics

ASS input is parsed into a Document. Track configurations select lyrics and
prepare Scene content; custom Scene objects can be added before compilation.
Input text, singing clocks, and source records remain separate from appearance.
The [Track guide](docs/guides/tracks.md) explains this workflow.

Apply a recipe with `kara-templater input.ass output.ass --effect my_effect.py`.
See [CLI usage](docs/guides/cli.md).

## Output and development

The ASS output loads as an ordinary subtitle file. For GPU playback or video
production, export a [standalone libplacebo shader](docs/guides/gpu-rendering.md). Fonts, renderer support, and
event complexity affect playback; see [ASS and playback](docs/ass-and-playback.md).
Complex effects expose budgets and explicit output choices.

[Contributing](docs/contributing/README.md) covers development setup, architecture,
testing, and release builds. The project and bundled native components have
separate license notices in [THIRD_PARTY.md](THIRD_PARTY.md).
