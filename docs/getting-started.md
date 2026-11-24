# Export your first karaoke subtitles

Both examples export a libplacebo Hook. You need Python 3.12 or newer and a
source checkout. To render a preview, use FFmpeg with libplacebo, libx264, and
a working Vulkan driver.
[Font setup](guides/fonts-and-preview.md) · [GPU setup](guides/gpu-rendering.md)

## Install from the checkout

1. Install the native build prerequisites for your platform.
   [Linux setup](contributing/setup.md#linux) · [Windows setup](contributing/setup.md#windows)
2. From the repository root, create a virtual environment.

   ```sh
   python -m venv .venv
   ```

3. Activate it with `source .venv/bin/activate` on Linux or
   `.\.venv\Scripts\Activate.ps1` in PowerShell. Install the checkout.

   ```sh
   python -m pip install .
   ```

These commands use the 1.1.0 exporter in this checkout. If you installed the 1.0.1 release from PyPI, use its versioned instructions. [Version 1.0.1 README](https://github.com/sitiyou/python-kara-templater/blob/v1.0.1/README.md)

## Apply a preset

From the repository root, apply the default preset to the included timed lyrics.
This sample uses DejaVu Sans.

```sh
kara-templater examples/karaoke.ass karaoke.hook
```

[Preset options and effect files](guides/cli.md)

## Write an effect

Save the script as `chorus.py` and run `python chorus.py`. ASS record times
use milliseconds. Inline `\k` values mark syllable lengths in centiseconds,
and `|` attaches a ruby reading. Use a font with Japanese glyphs. To select a
particular family, set `Style.fontname`.

```python
from kara_templater import (
    Color, Document, KaraokeEffects, Layout, Line, Style, Track, Vec2, build_lyric_scene,
)

song = Document.create(
    width=640,
    height=360,
    styles=(Style(fontsize=72, bold=True, outline=3, shadow=0),),
)
song.records.append(
    Line(start_time=0, end_time=3000, text=r"{\k90}星|ほし{\k45}に{\k165}届け|とどけ")
)
gold = KaraokeEffects.duotone(before_fill=Color.hex("#281C26"), after_fill=Color.hex("#FFE09A"))
vocal = Track(id="vocal", layout=Layout(position=Vec2(80, 180)), effects=(gold,))
scene = build_lyric_scene(song, tracks=(vocal,))
scene.export("chorus.hook", fps=30)
```

## Preview the export

Render a four-second clip on a solid background. For `chorus.hook`, use
640 × 360 at 30 fps.

```sh
ffmpeg -init_hw_device vulkan=vk -f lavfi -i "color=c=0x181B24:s=640x360:r=30:d=4" -vf "libplacebo=custom_shader_path=chorus.hook" -c:v libx264 -pix_fmt yuv420p preview.mp4
```

For `karaoke.hook`, use `s=1280x720`, `r=60` and
`custom_shader_path=karaoke.hook` in the same command.
[Render over footage or play in mpv](guides/gpu-rendering.md)

## Export your own lyrics

Use your timed ASS file in the preset command, or load it with
`Document.load("song.ass")` in the effect script in place of creating a document
and adding the sample line. Both read the file's lyrics, timing and ruby.
Match the preview canvas and frame rate to your export.

[Supported lyric input](guides/documents.md#choose-the-lyric-frontend) · [Lay out lead and harmony vocals](tutorials/karaoke-design.md) · [Compare output formats](guides/choosing-output.md)
