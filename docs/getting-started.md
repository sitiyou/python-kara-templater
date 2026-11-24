# Export your first karaoke subtitles

Export the included timed lyrics and watch the syllables change color. You need
Python 3.12 or newer, a source checkout, and DejaVu Sans for the sample. To render
the preview, use FFmpeg with libplacebo, libx264, and a working Vulkan driver.
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

These commands use the exporter in this checkout. If you installed the 1.0.1
release from PyPI, use its versioned instructions. [Version 1.0.1 README](https://github.com/sitiyou/python-kara-templater/blob/v1.0.1/README.md)

## Export the sample

Run the CLI from the repository root. The input has four timed syllables and a
small reading above each one. The exporter writes `karaoke.hook` at 60 fps.

```sh
kara-templater examples/karaoke.ass karaoke.hook
```

## Preview the export

Render a four-second clip on a solid background. The 1280 × 720 canvas matches
the sample's ASS script, and the 60 fps input matches the hook.

```sh
ffmpeg -init_hw_device vulkan=vk -f lavfi -i "color=c=0x181B24:s=1280x720:r=60:d=4" -vf "libplacebo=custom_shader_path=karaoke.hook" -c:v libx264 -pix_fmt yuv420p preview.mp4
```

Open `preview.mp4`. The lyrics appear one second in and change from yellow to
white across four syllables. The fourth syllable finishes at three seconds.
[Render over footage or play in mpv](guides/gpu-rendering.md)

## Export your own lyrics

Replace `examples/karaoke.ass` with a timed ASS file. The preset uses the file's
secondary color for waiting text and its primary color for sung text. To choose
a different sung color, pass `--after` with a hex color. Use `--ass` to produce
a standard subtitle file for an ASS player.

```sh
kara-templater song.ass song.hook --after "#FFE09A"
kara-templater song.ass song-styled.ass --ass
```

[CLI options and reusable effects](guides/cli.md) · [Compare output formats](guides/choosing-output.md)

## Write an effect in Python

Save the script below as `chorus.py` and run `python chorus.py`. It creates
lyrics in Python and exports `chorus.hook`. ASS record times use milliseconds.
The inline `\k` values mark syllable lengths in centiseconds, and `|` attaches
a ruby reading to a syllable.

```python
from kara_templater import (
    Color, Document, KaraokeEffects, Layout, Line, Style, Track, Vec2, prepare_tracks,
)

song = Document.create(
    width=640,
    height=360,
    styles=(Style(fontsize=72, bold=True, outline=3, shadow=0),),
)
song.records.append(
    Line(start_time=0, end_time=3000, text=r"{\k90}星|ほし{\k45}に{\k165}届け|とどけ")
)
gold = KaraokeEffects.duotone(unsung=Color.hex("#281C26"), sung=Color.hex("#FFE09A"))
vocal = Track(id="vocal", layout=Layout(position=Vec2(80, 180)), effects=(gold,))
scene = prepare_tracks(song, tracks=(vocal,))
scene.export("chorus.hook", fps=30)
```

Install a font with Japanese glyphs and set `Style.fontname` to its family for
this example. To preview the gold sweep through the lyric and its readings,
render `chorus.hook` with a 640 × 360 canvas at 30 fps.

[Lay out lead and harmony vocals](tutorials/karaoke-design.md) · [Browse reusable effects](examples/README.md)
