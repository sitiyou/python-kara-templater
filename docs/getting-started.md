# Quickstart

Install kara-templater, turn timed lyrics into an animated karaoke scene, and preview it in your browser or over a video.

## Install

You need Python 3.12 or newer. Building from a source checkout also requires a C/C++ compiler, Cargo and Rust 1.87+, and development headers for FreeType, HarfBuzz, FriBidi, Fontconfig, and libpng. See [Development setup](contributing/setup.md) for Linux and Windows package commands.

From the repository root, create and activate a virtual environment, then install the package:

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install .
```

On Windows PowerShell, activate the environment with `.\.venv\Scripts\Activate.ps1`.

## Export with a preset

From the repository root, run the default preset against the bundled timed ASS sample:

```sh
kara-templater examples/karaoke.ass karaoke.hook
```

The sample uses a 1280 × 720 canvas with DejaVu Sans and four timed syllables with ruby readings. The command writes a 60 fps Hook (`karaoke.hook`) with a color wipe driven by the `\k` tags.

To customize wipe colors, fades, or syllable pulses from the command line, see [Command line](guides/cli.md).

## Write your first Python template

Save the following script as `chorus.py` and run `python chorus.py`. It creates a timed Japanese line with ruby readings and exports `chorus.hook`, sweeping each syllable from dark plum to warm gold.

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

Here is how the pieces connect:

- `Document.create(...)` creates a 640 × 360 canvas with one style (`shadow=0` disables the default drop shadow).
- `Line(...)` defines a lyric line from 0 ms to 3000 ms. Inside `text`, `\k90` gives the first syllable 90 centiseconds (0.9 s), and `星|ほし` attaches the reading `ほし` to `星`.
- `KaraokeEffects.duotone(...)` creates a two-color feathered wipe between `before_fill` and `after_fill`.
- `Track(...)` places the line at `(80, 180)` and applies the effect.
- `build_lyric_scene(...)` measures glyphs and builds a `Scene`. `scene.export("chorus.hook", fps=30)` packages a playback shader at 30 fps for the mpv and FFmpeg commands below.

Try changing `before_fill` or `after_fill` to match your footage, or swap `gold` for `KaraokeEffects(entry="rise", exit="fade")` to add line transitions.

> [!NOTE]
> This script uses Japanese characters. Install a font with Japanese glyphs (such as Noto Sans CJK JP or Sarasa UI J) if characters render as missing-glyph boxes. See [Choose and register fonts](guides/fonts.md).

## Preview in your browser

Add this line after building the scene and run `python chorus.py` again:

```python
scene.preview()
```

Use the controls to play or scrub the scene. The player opens a local HTML file and renders it in WebGL 2.

## Preview the Hook

Play the Hook directly over a matching-aspect video in mpv:

```sh
mpv --vo=gpu-next --sub-auto=no --glsl-shader=chorus.hook video.mp4
```

To inspect the result on a plain background without video footage, render four seconds with FFmpeg using the `libplacebo` filter and Vulkan. Match the canvas size (`640x360`) and frame rate (`30`) to the export:

```sh
ffmpeg -init_hw_device vulkan=vk \
  -f lavfi -i "color=c=0x181B24:s=640x360:r=30:d=4" \
  -vf "libplacebo=custom_shader_path=chorus.hook" \
  -c:v libx264 -pix_fmt yuv420p preview.mp4
```

To preview `karaoke.hook` from the CLI preset step, use `s=1280x720`, `r=60`, `d=5`, and `custom_shader_path=karaoke.hook`. See [Play and render a Hook](output/hook.md) for burning into real footage and exporting time windows.

## Use your own timed ASS file

Pass your own `.ass` file to the `kara-templater` command, or replace `Document.create(...)` and `song.records.append(...)` in `chorus.py` with:

```python
song = Document.load("song.ass")
```

Both read the file's `PlayRes`, timing tags, and ruby readings. Match your FFmpeg preview resolution and frame rate to the loaded file and `scene.export(..., fps=...)`.

## Next steps

- [Core concepts](concepts.md) — Learn how time units, coordinates, lifetimes, and outputs fit together.
- [Design a song layout](tutorials/karaoke-design.md) — Lay out lead and harmony vocals with automatic row rotation.
- [Import timed lyrics](guides/documents.md) — Check all supported `\k` timing, ruby, and continuation syntax.
- [Preview and export](output/README.md) — Choose browser preview, shader playback, or standard ASS.
