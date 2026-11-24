# kara-templater documentation

## Make your first karaoke export

- [Export and preview the sample](getting-started.md)
- [Style your own timed ASS file from the command line](guides/cli.md)
- [Write your first effect in Python](getting-started.md#write-an-effect-in-python)
- [Choose between a subtitle file and a GPU hook](guides/choosing-output.md)

## Build a reusable template

- [Lay out lead and harmony vocals](tutorials/karaoke-design.md)
- [Pick an effect by its preview](examples/README.md) or [choose a built-in animation](guides/karaoke-effects.md)
- [Import timed lyrics](guides/documents.md) and [configure Tracks](guides/tracks.md)
- [Place ruby readings and count-ins](guides/text-and-cues.md)
- [Write a custom animation](tutorials/custom-animation.md), [animate singing highlights](tutorials/lyric-highlights.md), or [adapt a motion study](tutorials/lyric-studies.md)
- [Follow the template authoring skill](../skills/kara-templater/SKILL.md) when building a template with a coding agent

## Render or troubleshoot an export

- [Render with FFmpeg or play a hook in mpv](guides/gpu-rendering.md)
- [Compile standard ASS](guides/compilation.md) and [check player compatibility](ass-and-playback.md)
- [Install fonts and verify glyph positions](guides/fonts-and-preview.md)
- [Diagnose export and rendering errors](guides/troubleshooting.md)

## Look up the API

Use the [Python API reference](reference/README.md) for signatures and contracts.
The guides explain how to combine [scene objects](guides/objects.md),
[animation clocks](guides/animation.md), [geometry and masks](guides/geometry.md),
[materials](guides/materials.md), and [particles](guides/particles.md).

[Contribute to the project](contributing/README.md)
