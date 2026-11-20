# kara-templater

Design karaoke in Python from timed lyrics. A Track can lay out readings above
the words, sweep color through a held note, and animate each syllable on its
own clock. Export the prepared scene as a standard ASS subtitle or a standalone
libplacebo hook for mpv and FFmpeg.

## Sweep color through a lyric and its readings

![Gold sweeps through 星に届け and its readings as each note is sung](docs/examples/assets/chorus-hook.gif)

This hook preview follows three notes in *星に届け*. The fill and outline
change together as the singer moves across each glyph. The example includes
its own lyrics. For an existing song, load its timed ASS with `Document.load`.

```python
from kara_templater import (
    Color, Document, KaraokeEffects, Layout, Line, Style, Track, Vec2, prepare_tracks,
)

vocal = Style(fontname="Sarasa UI J", fontsize=72, bold=True, outline=3, shadow=0)
song = Document.create(width=640, height=360, styles=(vocal,))
song.records.append(Line(
    start_time=0, end_time=3000, text=r"{\k90}星|ほし{\k45}に{\k165}届け|とどけ",
))

ink = KaraokeEffects.duotone(unsung=Color.hex("#281C26"), sung=Color.hex("#FFE09A"))
scene = prepare_tracks(song, tracks=(
    Track(id="vocal", layout=Layout(rows=1, position=Vec2(80, 180)), effects=(ink,)),
))
scene.export_compact_ass("chorus.ass")
scene.export_hook("chorus.hook", fps=30)
```

The note lengths are 90, 45 and 165 centiseconds. The text after each `|` is
the reading to place above that unit. To change the look, adjust the sung
color. The soft boundary follows the font size of each lyric and reading. To see what survives each export,
[compare the same frame in compact ASS, compiled ASS and hook](docs/guides/choosing-output.md#one-singing-position-three-renders).

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
