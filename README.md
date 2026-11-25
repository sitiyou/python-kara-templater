# kara-templater

Build animated karaoke scenes in Python, write custom effects in WGSL, and preview them live in a browser.

![Japanese lyrics and their readings fill with gold as the highlight sweeps across each syllable](docs/examples/assets/chorus-hook.gif)

[Documentation overview](docs/README.md) · [Quickstart](docs/getting-started.md) · [Core concepts](docs/concepts.md) · [Example scripts](docs/examples/README.md) · [API reference](docs/reference/README.md) · [简体中文文档](docs/zh-cn/README.md)

## What it does

`kara-templater` reads timed ASS lyrics (`\k` tags, ruby readings, and cues), shapes real font glyphs with FreeType and HarfBuzz, and lets you author reusable karaoke templates in Python.

Every template follows the same four-step pipeline:

1. **`Document`** holds your script resolution (`PlayRes`), styles, and timed lyric lines.
2. **`Track`** selects a vocal part (such as lead or harmony), places rows or columns, and applies built-in or custom effects.
3. **`Scene`** collects the measured lyric lines and any extra text, shapes, or groups into one renderable composition.
4. **Preview or export** compiles WGSL materials to GLSL with Naga. Open a real-time WebGL 2 preview, package the shader and its textures for mpv or FFmpeg, or compile standard ASS for subtitle compatibility.

## Quick install and first export

Install Python 3.12 or newer along with the platform build prerequisites listed in [Development setup](docs/contributing/setup.md), then install from the repository root inside a virtual environment:

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install .
```

Apply the built-in CLI preset to the bundled sample lyrics to export a 60 fps Hook:

```sh
kara-templater examples/karaoke.ass karaoke.hook
```

Or build a `Scene` in Python to control colors, placement, ruby readings, and animations:

```python
from kara_templater import (
    Color,
    Document,
    KaraokeEffects,
    Layout,
    Line,
    Style,
    Track,
    Vec2,
    build_lyric_scene,
)

song = Document.create(
    width=640,
    height=360,
    styles=(Style(fontsize=72, bold=True, outline=3, shadow=0),),
)
song.records.append(
    Line(start_time=0, end_time=3000, text=r"{\k90}星|ほし{\k45}に{\k165}届け|とどけ")
)
gold = KaraokeEffects.duotone(
    before_fill=Color.hex("#281C26"),
    after_fill=Color.hex("#FFE09A"),
)
vocal = Track(id="vocal", layout=Layout(position=Vec2(80, 180)), effects=(gold,))
scene = build_lyric_scene(song, tracks=(vocal,))
scene.export("chorus.hook", fps=30)
```

Call `scene.preview()` to open the scene in your browser. The exported `.hook` can play over video in mpv or be rendered into a video with FFmpeg. See the [Quickstart](docs/getting-started.md) and [Preview and export](docs/output/README.md).

## Explore the docs

- **Start here**: [Overview](docs/README.md) · [Quickstart](docs/getting-started.md) · [Core concepts](docs/concepts.md) · [Example scripts](docs/examples/README.md)
- **Learn by building**: [Tutorials](docs/tutorials/README.md) · [Design a song layout](docs/tutorials/karaoke-design.md) · [Effect recipes](docs/tutorials/effect-recipes.md)
- **Task guides & reference**: [Guides](docs/guides/README.md) · [Command line](docs/guides/cli.md) · [Preview and export](docs/output/README.md) · [API reference](docs/reference/README.md)
- **中文用户**：从[简体中文文档概览](docs/zh-cn/README.md)开始阅读完整中文教程与指南。

[Contributing](docs/contributing/README.md) · [MIT license](LICENSE) · [Third-party notices](THIRD_PARTY.md)
