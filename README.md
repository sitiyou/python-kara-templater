# kara-templater

Turn timed lyrics into animated karaoke subtitles. Apply a preset or build
effects for lead and harmony vocals, ruby readings, and syllable highlights.
Export a standalone libplacebo Hook for playback or video rendering.

![Japanese lyrics and their readings fill with gold as the highlight sweeps across each syllable](docs/examples/assets/chorus-hook.gif)

[Getting started](docs/getting-started.md) · [Effect gallery](docs/examples/README.md) · [Documentation](docs/README.md)

## Quick start

With Python 3.12 or newer and the platform build prerequisites installed, install
from the repository root in a virtual environment.
[Build prerequisites](docs/contributing/setup.md)

```sh
python -m pip install .
```

Try a preset on timed ASS or build a Scene with your own effects. Play the Hook
in mpv or render it with FFmpeg. [Apply a preset](docs/getting-started.md#apply-a-preset) · [Write an effect](docs/getting-started.md#write-an-effect) · [Preview](docs/getting-started.md#preview-the-export)

To write your own effect, start with a Track for each vocal part. Use the built-in
entry, highlight, and exit effects or add your own Scene objects.
[Design a template](docs/tutorials/karaoke-design.md) · [API reference](docs/reference/README.md) · [CLI guide](docs/guides/cli.md)

[Contributing](docs/contributing/README.md) · [MIT license](LICENSE) · [Third-party notices](THIRD_PARTY.md)
