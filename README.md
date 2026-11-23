# kara-templater

A Python library for turning timed lyrics into animated karaoke subtitles.
Arrange vocals and ruby readings on separate rows, sweep colour through each sung syllable,
and export the result as ASS subtitles or a standalone libplacebo hook for mpv and FFmpeg.

![Gold sweeps through 星に届け and its readings in time with three sung notes](docs/examples/assets/chorus-hook.gif)

[Getting started](docs/getting-started.md) · [Effect gallery](docs/examples/README.md) · [Documentation](docs/README.md) · [For AI agents](#for-ai-agents)

## Render the example

This example uses inline ASS timing for brevity. Templates can also consume structured lyrics directly. With Python 3.12 or later and the library installed, run:

```python
from kara_templater import (
    Color, Document, KaraokeEffects, Layout, Line, Style, Track, Vec2, prepare_tracks,
)

vocal = Style(fontsize=72, bold=True, outline=3, shadow=0)
song = Document.create(width=640, height=360, styles=(vocal,))
song.records.append(
    Line(start_time=0, end_time=3000, text=r"{\k90}星|ほし{\k45}に{\k165}届け|とどけ")
)

gold = KaraokeEffects.duotone(unsung=Color.hex("#281C26"), sung=Color.hex("#FFE09A"))
vocal_track = Track(id="vocal", layout=Layout(rows=1, position=Vec2(80, 180)), effects=(gold,))
scene = prepare_tracks(song, tracks=(vocal_track,))

scene.export_hook("chorus.hook", fps=30)
```

Play `chorus.hook` with mpv’s GPU renderer. For standard ASS, set
`feather=0` on the duotone recipe and save `scene.compile().document`.
[Choose an output](docs/guides/choosing-output.md).

## Use your own lyrics

Create lyric lines directly in Python, as in the example above, or load an existing
karaoke ASS file with `Document.load("song.ass")`. For structured lyrics with explicit
singing intervals and ruby, build a `DocumentLyrics`, wrap it with `LyricSource.from_lyrics`,
and pass the sources to `prepare_tracks` through `inputs=`. [Track guide](docs/guides/tracks.md)

To reuse an effect across songs, put its Track configuration or scene builder in a Python
file and run `kara-templater song.ass styled.ass --effect my_effect.py`.
[CLI and effect file examples](docs/guides/cli.md)

## For AI agents

When asked to create or revise a karaoke template, start with the [template authoring skill](skills/kara-templater/SKILL.md).
It pairs tasks such as fixing a crowded row or adding particles with working Python examples
and identifies the frames to check in the exported result.

## Project

[Contributing](docs/contributing/README.md) · [MIT license](LICENSE) · [Third-party notices](THIRD_PARTY.md)
