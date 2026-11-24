# kara-templater

Turn timed lyrics into animated karaoke subtitles. Style an existing ASS file
from the command line, or write Python effects for lead and harmony vocals,
ruby readings, and syllable highlights.

![Japanese lyrics and their readings fill with gold as the highlight sweeps across each syllable](docs/examples/assets/chorus-hook.gif)

[Getting started](docs/getting-started.md) · [Effect gallery](docs/examples/README.md) · [Documentation](docs/README.md)

## Quick start

With Python 3.12 or newer and the platform build prerequisites installed, run
these commands from the repository root in a virtual environment.
[Build prerequisites](docs/contributing/setup.md)

```sh
python -m pip install .
kara-templater examples/karaoke.ass karaoke.hook
```

This exports the included timed lyrics as a libplacebo hook for mpv or FFmpeg.
For standard ASS, run `kara-templater examples/karaoke.ass karaoke-styled.ass --ass`.
The first-export tutorial shows how to render the sample over a plain background
and replace it with your own lyrics. [Play your first export](docs/getting-started.md#preview-the-export)

To write your own effect, start with a Track for each vocal part. Use the built-in
entry, highlight, and exit effects or add your own Scene objects.
[Design a template](docs/tutorials/karaoke-design.md) · [Python API](docs/reference/README.md)

[Contributing](docs/contributing/README.md) · [MIT license](LICENSE) · [Third-party notices](THIRD_PARTY.md)
